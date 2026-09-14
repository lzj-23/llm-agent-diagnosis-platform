"""Materialize deterministic synthetic-v2 cases and labels with hashes."""

import hashlib
import json
from pathlib import Path

from diagnosis_agent.evaluation.synthetic import SPLIT_COUNTS, generate_split, validate_generated

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data/synthetic-v2"


def digest(data):
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


for split, expected_count in SPLIT_COUNTS.items():
    rows = generate_split(split)
    issues = validate_generated(rows)
    if issues or len(rows) != expected_count:
        raise RuntimeError(json.dumps({"split": split, "issues": issues}))
    cases = [row.case.model_dump() for row in rows]
    labels = [row.label for row in rows]
    folder = OUTPUT / split
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cases.json").write_text(
        json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "dataset": "synthetic-v2 deterministic causal fixtures; not real incidents",
        "split": split,
        "case_count": len(cases),
        "case_sha256": digest(cases),
        "label_sha256": digest(labels),
        "labels_are_not_passed_to_agent": True,
        "blind_independent_test": False,
        "issues": issues,
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(split, len(rows), manifest["case_sha256"])
