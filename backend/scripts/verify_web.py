"""Paid model E2E verification against an already running local service."""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx


async def verify(base, folder):
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    async with httpx.AsyncClient(base_url=base, timeout=10) as client:
        assert (await client.get("/health")).status_code == 200
        homepage = await client.get("/")
        assert homepage.status_code == 200
        assert "text/html" in homepage.headers["content-type"]
        assert (await client.get("/assets/app.js")).status_code == 200
        for kind in ("latency", "oom", "config"):
            body = {
                "case_id": kind + "-0",
                "question": "分析本案例的异常与候选原因，必须提供证据。",
                "session_id": "container-acceptance",
                "mode": "multi",
            }
            key = str(uuid4())
            first = await client.post("/api/tasks", json=body, headers={"idempotency-key": key})
            first.raise_for_status()
            task_id = first.json()["id"]
            second = await client.post("/api/tasks", json=body, headers={"idempotency-key": key})
            assert second.json() == {"id": task_id, "created": False}
            for _ in range(180):
                response = await client.get("/api/tasks/" + task_id)
                response.raise_for_status()
                task = response.json()
                if task["status"] in ("completed", "needs_attention"):
                    break
                await asyncio.sleep(1)
            (folder / (kind + ".json")).write_text(
                json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            rows.append(
                {
                    "case": kind,
                    "task_id": task_id,
                    "status": task["status"],
                    "category": task.get("result", {}).get("diagnosis", {}).get("category"),
                }
            )
            print(rows[-1], flush=True)
            assert task["status"] == "completed"
            assert task["result"]["diagnosis"]["category"] == kind
        (folder / "manifest.json").write_text(
            json.dumps(
                {"base": "local Compose service", "idempotency_verified": True, "cases": rows},
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:18080")
    p.add_argument("--output", default="evaluation-results/container-e2e")
    a = p.parse_args()
    asyncio.run(verify(a.base, Path(a.output)))
