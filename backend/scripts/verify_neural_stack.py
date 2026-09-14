"""One paid model task against the local neural Compose stack; retain failures."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx


async def verify(output):
    output.mkdir(parents=True, exist_ok=False)
    async with httpx.AsyncClient(base_url="http://127.0.0.1:18080", timeout=15) as client:
        for _ in range(30):
            try:
                if (await client.get("/health")).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
        else:
            raise RuntimeError("service_not_ready")
        root = await client.get("/")
        assert root.status_code == 200 and "text/html" in root.headers["content-type"]
        assert (await client.get("/assets/app.js")).status_code == 200
        response = await client.post(
            "/api/tasks",
            headers={"idempotency-key": str(uuid4())},
            json={
                "case_id": "oom-0",
                "question": "分析显存不足案例，必须使用 search_docs 检索显存相关技术文档，并引用检索证据。",
                "session_id": "neural-compose-verification",
                "mode": "multi",
                "rag": True,
                "reviewer": True,
            },
        )
        response.raise_for_status()
        task_id = response.json()["id"]
        for _ in range(240):
            task = (await client.get("/api/tasks/" + task_id)).json()
            if task["status"] in ("completed", "needs_attention"):
                break
            await asyncio.sleep(1)
        (output / "task.json").write_text(
            json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        searches = [e for e in task.get("events", []) if e.get("tool") == "search_docs"]
        backends = [e.get("output", {}).get("data", {}).get("backend") for e in searches]
        manifest = {
            "task_id": task_id,
            "status": task["status"],
            "retrieval_backends": backends,
            "homepage_and_assets": True,
            "dataset": "synthetic OOM fixture, real neural retrieval/model calls",
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest))
        assert "neural_sqlite_exact_cosine_crossencoder" in backends
        assert task["status"] == "completed"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    asyncio.run(verify(p.parse_args().output))
