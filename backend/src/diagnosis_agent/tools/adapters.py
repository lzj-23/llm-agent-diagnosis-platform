"""Read-only adapters; callers must explicitly supply an allowed root."""

import csv
import json
from pathlib import Path

from diagnosis_agent.security.guards import redact
from diagnosis_agent.tools.contracts import Log


def read_allowed(path: Path, root: Path) -> str:
    path = path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("path_outside_allowed_root")
    if path.stat().st_size > 10_000_000:
        raise ValueError("file_too_large")
    return path.read_text(encoding="utf-8-sig")


def rag_summary(path: Path, root: Path):
    data = json.loads(read_allowed(path, root))
    return {
        "dataset_size": data["dataset_size"],
        "metric_definition": data["metric_definition"],
        "configurations": data["configurations"],
        "note": "retrieval latency is not TTFT or generation latency",
    }


def read_logs(path: Path, root: Path):
    text = read_allowed(path, root)
    rows = (
        csv.DictReader(text.splitlines())
        if path.suffix.lower() == ".csv"
        else (json.loads(line) for line in text.splitlines() if line.strip())
    )
    return [Log.model_validate({**row, "message": redact(row["message"])}) for row in rows]
