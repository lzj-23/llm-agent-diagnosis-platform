"""Live PostgreSQL/Redis acceptance; creates only prefixed test records, no deletion."""

import concurrent.futures
import json
import os
from pathlib import Path
from uuid import uuid4

from redis import Redis

from diagnosis_agent.storage.repository import Conflict, Repository


def main():
    url = os.environ["TEST_DATABASE_URL"]
    repo = Repository(url)
    prefix = "acceptance-" + str(uuid4())
    ids = [
        repo.create({"session_id": prefix, "question": f"test {i}"}, prefix + str(i))[0]
        for i in range(8)
    ]

    def claim(i):
        owner = str(uuid4())
        task = repo.claim(owner)
        return task, owner

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(claim, range(8)))
    assert {t for t, _ in claimed} == set(ids)
    assert len({t for t, _ in claimed}) == 8
    for task, owner in claimed:
        repo.append_event(task, owner, {"action": "acceptance"})
        repo.finish(task, owner, {"status": "needs_attention", "error": "test_injected"})
    task = ids[0]
    assert repo.resume(task)
    assert repo.claim("expired", seconds=-1) == task
    assert repo.claim("replacement") == task
    try:
        repo.finish(task, "expired", {"status": "completed"})
        raise AssertionError("old_owner_not_fenced")
    except Conflict:
        pass
    repo.finish(
        task, "replacement", {"status": "completed", "diagnosis": {"conclusion": "acceptance"}}
    )
    repo.engine.dispose()
    assert Repository(url).get(task)["status"] == "completed"
    cache = Redis.from_url(os.environ["TEST_REDIS_URL"])
    cache.setex(prefix, 30, "ok")
    assert cache.get(prefix) == b"ok"
    result = {
        "postgres_concurrent_claims": 8,
        "unique_owners": True,
        "lease_recovery": True,
        "stale_worker_fenced": True,
        "reconnect_persistence": True,
        "redis_ttl_read_write": True,
        "test_record_prefix": prefix,
        "note": "test rows retained; Redis key expires after 30 seconds",
    }
    Path("evaluation-results/infrastructure.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
