import hashlib
import json
import time
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()
tasks = Table(
    "tasks",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("session_id", String(80)),
    Column("idempotency_key", String(120), unique=True),
    Column("fingerprint", String(64)),
    Column("payload", JSON),
    Column("status", String(30)),
    Column("result", JSON),
    Column("owner", String(36)),
    Column("lease_until", Float, default=0),
    Column("created_at", Float),
    Column("updated_at", Float),
)
events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", String(36), ForeignKey("tasks.id")),
    Column("event", JSON),
    Column("created_at", Float),
)
memories = Table(
    "memories",
    metadata,
    Column("task_id", String(36), ForeignKey("tasks.id"), primary_key=True),
    Column("session_id", String(80)),
    Column("summary", Text),
    Column("created_at", Float),
)


class Conflict(ValueError):
    pass


class Repository:
    def __init__(self, url):
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
        metadata.create_all(self.engine)

    def create(self, payload, key):
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        task_id, now = str(uuid4()), time.time()
        try:
            with self.engine.begin() as db:
                db.execute(
                    insert(tasks).values(
                        id=task_id,
                        session_id=payload["session_id"],
                        idempotency_key=key,
                        fingerprint=digest,
                        payload=payload,
                        status="pending",
                        result={},
                        owner=None,
                        lease_until=0,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError:
            with self.engine.connect() as db:
                existing = (
                    db.execute(select(tasks).where(tasks.c.idempotency_key == key)).mappings().one()
                )
            if existing["fingerprint"] != digest:
                raise Conflict("idempotency_key_reused") from None
            return existing["id"], False
        return task_id, True

    def get(self, task_id):
        with self.engine.connect() as db:
            row = db.execute(select(tasks).where(tasks.c.id == task_id)).mappings().first()
            return dict(row) if row else None

    def history(self, limit=30):
        with self.engine.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    select(tasks).order_by(tasks.c.created_at.desc()).limit(limit)
                ).mappings()
            ]

    def claim(self, owner, seconds=90):
        now = time.time()
        eligible = (tasks.c.status == "pending") | (
            (tasks.c.status == "running") & (tasks.c.lease_until < now)
        )
        with self.engine.begin() as db:
            query = select(tasks.c.id).where(eligible).order_by(tasks.c.created_at).limit(1)
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            row = db.execute(query).first()
            if not row:
                return None
            count = db.execute(
                update(tasks)
                .where(tasks.c.id == row.id, eligible)
                .values(status="running", owner=owner, lease_until=now + seconds, updated_at=now)
            ).rowcount
            return row.id if count else None

    def heartbeat(self, task_id, owner):
        with self.engine.begin() as db:
            return (
                db.execute(
                    update(tasks)
                    .where(
                        tasks.c.id == task_id, tasks.c.owner == owner, tasks.c.status == "running"
                    )
                    .values(lease_until=time.time() + 90)
                ).rowcount
                == 1
            )

    def append_event(self, task_id, owner, event):
        with self.engine.begin() as db:
            # Fencing write locks the task row; an expired worker cannot overwrite a new owner's result.
            allowed = db.execute(
                update(tasks)
                .where(tasks.c.id == task_id, tasks.c.owner == owner, tasks.c.status == "running")
                .values(updated_at=time.time())
            ).rowcount
            if not allowed:
                raise Conflict("lease_lost")
            db.execute(insert(events).values(task_id=task_id, event=event, created_at=time.time()))

    def trace(self, task_id):
        with self.engine.connect() as db:
            return [
                {"id": r.id, **r.event}
                for r in db.execute(
                    select(events).where(events.c.task_id == task_id).order_by(events.c.id)
                )
            ]

    def finish(self, task_id, owner, result):
        with self.engine.begin() as db:
            row = db.execute(select(tasks).where(tasks.c.id == task_id)).mappings().one()
            changed = db.execute(
                update(tasks)
                .where(tasks.c.id == task_id, tasks.c.owner == owner, tasks.c.status == "running")
                .values(
                    status=result["status"], result=result, updated_at=time.time(), lease_until=0
                )
            ).rowcount
            if not changed:
                raise Conflict("lease_lost")
            if result["status"] == "completed":
                db.execute(
                    insert(memories).values(
                        task_id=task_id,
                        session_id=row["session_id"],
                        summary=json.dumps(result["diagnosis"], ensure_ascii=False),
                        created_at=time.time(),
                    )
                )

    def resume(self, task_id):
        with self.engine.begin() as db:
            return (
                db.execute(
                    update(tasks)
                    .where(tasks.c.id == task_id, tasks.c.status == "needs_attention")
                    .values(status="pending", owner=None, lease_until=0, updated_at=time.time())
                ).rowcount
                == 1
            )

    def recall(self, session_id, question):
        from diagnosis_agent.rag.knowledge import tokens

        q = set(tokens(question))
        with self.engine.connect() as db:
            rows = (
                db.execute(select(memories).order_by(memories.c.created_at.desc()).limit(100))
                .mappings()
                .all()
            )
        short = [r["summary"] for r in rows if r["session_id"] == session_id][:3]
        long = sorted(rows, key=lambda r: -len(q & set(tokens(r["summary"]))))[:2]
        return json.dumps(
            {"session": short, "historical": [r["summary"] for r in long]}, ensure_ascii=False
        )[:4000]
