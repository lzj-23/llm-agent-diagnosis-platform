import argparse
import asyncio
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from diagnosis_agent.agents.engine import Engine
from diagnosis_agent.config import get_settings
from diagnosis_agent.tools.fixtures import cases


async def evaluate(output, modes, count):
    output.mkdir(parents=True, exist_ok=True)
    source_root = Path(__file__).resolve().parents[1]

    def fingerprint():
        digest = hashlib.sha256()
        for file in sorted(source_root.rglob("*.py")):
            digest.update(file.relative_to(source_root).as_posix().encode())
            digest.update(file.read_bytes())
        return digest.hexdigest()

    source_hash = fingerprint()
    rows = []
    for variant, mode, rag, reviewer in modes:
        for case in list(cases().values()):
            if int(case.id.rsplit("-", 1)[1]) >= count:
                continue
            result = await Engine().run(case.description, case.id, mode, rag, reviewer)
            name = f"{variant}-{case.id}"
            (output / (name + ".json")).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            diagnosis = result.get("diagnosis", {})
            row = {
                "variant": variant,
                "case_id": case.id,
                "expected": case.expected,
                "predicted": diagnosis.get("category", "unknown"),
                "completed": result["status"] == "completed",
                "root_cause_hit": diagnosis.get("category") == case.expected,
                "duration_ms": result["duration_ms"],
                "tokens": sum(x["prompt_tokens"] + x["completion_tokens"] for x in result["usage"]),
                "estimated_cny": sum(x["estimated_cny"] for x in result["usage"]),
                "error": result.get("error", ""),
            }
            rows.append(row)
            print(name, row["completed"], row["predicted"], row["error"], flush=True)
    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "dataset": "synthetic rule-generated cases; not independent real-world validation",
                "source_sha256": source_hash,
                "source_unchanged": source_hash == fingerprint(),
                "python": sys.version.split()[0],
                "model": get_settings().llm_model,
                "rows": len(rows),
                "modes": modes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evaluation-results/smoke")
    parser.add_argument("--count", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    modes = [("single", "single", True, False)]
    if args.full:
        modes += [
            ("multi", "multi", True, True),
            ("no-rag", "multi", False, True),
            ("no-reviewer", "multi", True, False),
        ]
    asyncio.run(evaluate(Path(args.output), modes, args.count))
