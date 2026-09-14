"""Run after intentionally restarting app or stopping optional Redis in local Compose."""

import argparse
import json
import time
from pathlib import Path

import httpx

p = argparse.ArgumentParser()
p.add_argument("label", choices=["after-restart", "redis-unavailable", "redis-restored"])
a = p.parse_args()
folder = Path("evaluation-results/container-e2e")
manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
with httpx.Client(base_url="http://127.0.0.1:18080", timeout=5) as client:
    for attempt in range(20):
        try:
            client.get("/health").raise_for_status()
            break
        except httpx.HTTPError:
            if attempt == 19:
                raise
            time.sleep(1)
    verified = []
    for row in manifest["cases"]:
        response = client.get("/api/tasks/" + row["task_id"])
        response.raise_for_status()
        task = response.json()
        assert task["status"] == "completed"
        assert task["result"]["diagnosis"]["category"] == row["case"]
        verified.append(task["id"])
result = {"label": a.label, "verified_completed_records": len(verified), "task_ids": verified}
(folder / (a.label + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))
