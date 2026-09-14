import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from redis.asyncio import Redis

from diagnosis_agent import __version__
from diagnosis_agent.config import get_settings
from diagnosis_agent.security.guards import UnsafeInput, sanitize, validate_question
from diagnosis_agent.storage.repository import Conflict, Repository
from diagnosis_agent.storage.worker import work
from diagnosis_agent.tools.contracts import Case, StrictModel
from diagnosis_agent.tools.service import ToolService


class TaskRequest(StrictModel):
    question: str = Field(min_length=2, max_length=2000)
    case_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    session_id: str = Field(default="demo", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    mode: Literal["single", "multi"] = "multi"
    rag: bool = True
    reviewer: bool = True


def create_app(settings=None, start_workers=True):
    settings = settings or get_settings()
    runtime = Path(settings.runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)
    repo = Repository(settings.database_url or "sqlite:///" + str(runtime / "tasks.sqlite"))
    cache = (
        Redis.from_url(settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        if settings.redis_url
        else None
    )

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()
        workers = (
            [asyncio.create_task(work(repo, stop, cache)) for _ in range(settings.worker_count)]
            if start_workers
            else []
        )
        yield
        stop.set()
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        if cache:
            await cache.aclose()
        repo.engine.dispose()

    app = FastAPI(title="LLM Agent Diagnosis Platform", version=__version__, lifespan=lifespan)
    app.state.repo = repo

    @app.middleware("http")
    async def access(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            if settings.web_api_key and not secrets.compare_digest(
                request.headers.get("x-api-key", ""), settings.web_api_key
            ):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse({"error": "origin_not_allowed"}, status_code=403)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"error": "invalid_content_length"}, status_code=400)
            if length > 1_000_000:
                return JSONResponse({"error": "body_too_large"}, status_code=413)
            if request.method in ("POST", "PUT", "PATCH"):
                total = 0
                parts = []
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > 1_000_000:
                        return JSONResponse({"error": "body_too_large"}, status_code=413)
                    parts.append(chunk)
                request._body = b"".join(parts)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "service": settings.app_name, "version": __version__}

    @app.get("/api/cases")
    def list_cases():
        return [
            {"id": c.id, "description": c.description, "synthetic": c.synthetic}
            for c in ToolService(settings=settings).dataset.values()
        ]

    @app.post("/api/cases", status_code=201)
    def import_case(case: Case):
        folder = runtime / "cases"
        folder.mkdir(exist_ok=True)
        if case.id in ToolService(settings=settings).dataset:
            raise HTTPException(409, "case_id_exists")
        case.expected = "unknown"
        case = Case.model_validate(sanitize(case.model_dump()))
        try:
            with (folder / (case.id + ".json")).open("x", encoding="utf-8") as f:
                f.write(case.model_dump_json())
        except FileExistsError:
            raise HTTPException(409, "case_id_exists") from None
        return {"id": case.id}

    @app.post("/api/tasks", status_code=202)
    def submit(body: TaskRequest, request: Request):
        try:
            body.question = validate_question(body.question)
        except UnsafeInput as exc:
            raise HTTPException(422, str(exc)) from None
        if body.case_id not in ToolService(settings=settings).dataset:
            raise HTTPException(404, "case_not_found")
        key = request.headers.get("idempotency-key", str(uuid4()))
        if len(key) > 120:
            raise HTTPException(422, "idempotency_key_too_long")
        try:
            task_id, created = repo.create(body.model_dump(), key)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from None
        return {"id": task_id, "created": created}

    @app.get("/api/tasks")
    def history():
        return [
            {k: r[k] for k in ("id", "payload", "status", "created_at", "updated_at")}
            for r in repo.history()
        ]

    @app.get("/api/tasks/{task_id}")
    async def task(task_id: str):
        key = "task:" + task_id
        if cache:
            try:
                cached = await cache.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:  # noqa: BLE001 -- optional cache fallback
                logging.getLogger(__name__).warning("redis_read_unavailable")
        record = await asyncio.to_thread(repo.get, task_id)
        if not record:
            raise HTTPException(404, "task_not_found")
        record["events"] = await asyncio.to_thread(repo.trace, task_id)
        if cache:
            try:
                await cache.setex(key, 1, json.dumps(record))
            except Exception:  # noqa: BLE001 -- database remains authoritative
                logging.getLogger(__name__).warning("redis_write_unavailable")
        return record

    @app.post("/api/tasks/{task_id}/resume")
    def resume(task_id: str):
        if not repo.resume(task_id):
            raise HTTPException(409, "task_not_resumable")
        return {"id": task_id, "status": "pending"}

    @app.get("/api/tasks/{task_id}/events")
    async def stream(task_id: str, request: Request):
        if not repo.get(task_id):
            raise HTTPException(404, "task_not_found")

        async def rows():
            seen = 0
            while not await request.is_disconnected():
                for row in await asyncio.to_thread(repo.trace, task_id):
                    if row["id"] > seen:
                        seen = row["id"]
                        yield "data: " + json.dumps(row, ensure_ascii=False) + "\n\n"
                current = await asyncio.to_thread(repo.get, task_id)
                if current["status"] in ("completed", "needs_attention"):
                    yield "event: done\ndata: " + json.dumps({"status": current["status"]}) + "\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(rows(), media_type="text/event-stream")

    @app.get("/api/evaluation")
    def evaluation():
        folder = Path(settings.project_root) / "evaluation-results"
        return [
            {
                "run": p.parent.name,
                "manifest": json.loads(p.read_text(encoding="utf-8")),
                "summary": json.loads((p.parent / "summary.json").read_text(encoding="utf-8"))
                if (p.parent / "summary.json").exists()
                else None,
            }
            for p in folder.glob("*/manifest.json")
        ]

    frontend = Path(settings.project_root) / "frontend"
    if (frontend / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=frontend), name="assets")

        @app.get("/")
        def index():
            return FileResponse(frontend / "index.html")

    return app
