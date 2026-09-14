"""Authored challenge-set check, not a held-out production benchmark."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from diagnosis_agent.agents.grounding import check_grounding
from diagnosis_agent.agents.model import ModelClient

ROOT = Path(__file__).resolve().parents[2]


async def evaluate(output):
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").exists():
        raise ValueError("choose_a_new_output_directory")
    source = ROOT / "data/grounding_challenges.json"
    cases = json.loads(source.read_text(encoding="utf-8"))
    source_root = ROOT / "backend/src/diagnosis_agent"

    def fingerprint():
        digest = hashlib.sha256()
        for file in sorted(source_root.rglob("*.py")):
            digest.update(file.relative_to(source_root).as_posix().encode())
            digest.update(file.read_bytes())
        return digest.hexdigest()

    before, rows = fingerprint(), []
    for case in cases:
        model, events = ModelClient(), []

        async def invoke(role, messages, model=model):
            return await model.chat(messages)

        def event(role, action, events=events, **data):
            events.append({"role": role, "action": action, **data})

        report = {
            "conclusion": case["claim"],
            "evidence_ids": ["sample"],
            "recommendations": [],
            "verification": [],
            "uncertainty": "",
        }
        issues = await check_grounding(report, {"sample": case["evidence"]}, invoke, event)
        available = not any(row["code"] == "grounding_unavailable" for row in issues)
        blocked = bool(issues)
        row = {
            "id": case["id"],
            "expected_block": case["expected_block"],
            "blocked": blocked,
            "available": available,
            "matches_rubric": available and blocked == case["expected_block"],
            "case": case,
            "events": events,
            "usage": model.usage,
        }
        (output / (case["id"] + ".json")).write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows.append(
            {k: row[k] for k in ("id", "expected_block", "blocked", "available", "matches_rubric")}
        )
        print(case["id"], row["matches_rubric"], flush=True)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": "8 authored development challenges; same provider/model; not blind independent validation",
                "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "source_sha256": before,
                "source_unchanged": before == fingerprint(),
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evaluation-results/grounding-v1")
    asyncio.run(evaluate(ROOT / parser.parse_args().output))
