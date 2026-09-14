"""Run one frozen synthetic case per scenario without exposing evaluator labels."""

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
from diagnosis_agent.evaluation.synthetic import SCENARIOS, generate_split

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "backend/src/diagnosis_agent"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def source_fingerprint():
    fingerprint = hashlib.sha256()
    for file in sorted(SOURCE_ROOT.rglob("*.py")):
        fingerprint.update(file.relative_to(SOURCE_ROOT).as_posix().encode())
        fingerprint.update(file.read_bytes())
    return fingerprint.hexdigest()


def select_rows():
    frozen = generate_split("frozen")
    return [next(row for row in frozen if row.label["scenario"] == name) for name in SCENARIOS]


async def evaluate(output):
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"output_not_empty:{output}")
    output.mkdir(parents=True, exist_ok=True)
    case_folder = Path(get_settings().runtime_dir) / "cases"
    case_folder.mkdir(parents=True, exist_ok=True)
    selected = select_rows()
    staged = []
    for row in selected:
        target = case_folder / f"{row.case.id}.json"
        if target.exists():
            raise RuntimeError(f"staging_target_exists:{target}")
        target.write_text(row.case.model_dump_json(indent=2), encoding="utf-8")
        staged.append(target)

    source_before = source_fingerprint()
    results = []
    try:
        for row in selected:
            result = await Engine().run(
                row.case.description,
                row.case.id,
                mode="single",
                rag=True,
                reviewer=False,
            )
            (output / f"{row.case.id}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            diagnosis = result.get("diagnosis", {})
            selected_tools = {
                event.get("tool")
                for event in result["events"]
                if event.get("role") == "executor" and event.get("action") == "tool"
            }
            fallback_tools = {
                event.get("tool")
                for event in result["events"]
                if event.get("source") == "mandatory_evidence_fallback"
            }
            required = set(row.label["required_tools"])
            conclusion = diagnosis.get("conclusion", "")
            exact_forbidden = [
                phrase for phrase in row.label["forbidden_claims"] if phrase in conclusion
            ]
            result_row = {
                "case_id": row.case.id,
                "scenario": row.label["scenario"],
                "expected_category": row.label["expected_category"],
                "predicted_category": diagnosis.get("category", "unknown"),
                "category_hit": diagnosis.get("category") == row.label["expected_category"],
                "completed": result["status"] == "completed",
                "required_tool_coverage": required <= set(result.get("tools", [])),
                "model_selected_required_tools": len(required & selected_tools),
                "required_tool_count": len(required),
                "fallback_tools": ",".join(sorted(fallback_tools)),
                "exact_forbidden_phrase_count": len(exact_forbidden),
                "quality_issue_count": len(result.get("quality_issues", [])),
                "duration_ms": round(result["duration_ms"], 1),
                "tokens": sum(
                    usage["prompt_tokens"] + usage["completion_tokens"] for usage in result["usage"]
                ),
                "estimated_cny": round(sum(usage["estimated_cny"] for usage in result["usage"]), 6),
                "error": result.get("error", ""),
            }
            results.append(result_row)
            print(
                row.case.id,
                result_row["completed"],
                result_row["predicted_category"],
                result_row["category_hit"],
                flush=True,
            )
    finally:
        for target in staged:
            target.unlink(missing_ok=True)

    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    summary = {
        "cases": len(results),
        "completed": sum(row["completed"] for row in results),
        "category_hits": sum(row["category_hit"] for row in results),
        "required_tool_coverage": sum(row["required_tool_coverage"] for row in results),
        "exact_forbidden_phrase_hits": sum(row["exact_forbidden_phrase_count"] for row in results),
        "tokens": sum(row["tokens"] for row in results),
        "estimated_cny": round(sum(row["estimated_cny"] for row in results), 6),
    }
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "synthetic-v2 frozen smoke; deterministic developer-authored fixtures",
        "selection": "first frozen case from each of eight scenario families",
        "agent_input": "case description plus MCP tool evidence; labels excluded",
        "case_sha256": digest([row.case.model_dump() for row in selected]),
        "label_sha256": digest([row.label for row in selected]),
        "source_sha256": source_before,
        "source_unchanged": source_before == source_fingerprint(),
        "python": sys.version.split()[0],
        "model": get_settings().llm_model,
        "mode": "single-agent with lexical RAG and final grounding audit",
        "blind_independent_test": False,
        "semantic_rubric_scored": False,
        "metric_limits": [
            "Category hit is coarse and does not prove the causal explanation is correct.",
            "Forbidden-claim matching is exact text only, not a semantic safety score.",
            "Mandatory tool coverage may include orchestrator fallback calls.",
        ],
        "summary": summary,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evaluation-results/synthetic-v2-frozen-smoke")
    arguments = parser.parse_args()
    asyncio.run(evaluate(Path(arguments.output)))
