"""Compute reproducible metrics; citation existence is NOT semantic correctness."""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from diagnosis_agent.tools.service import CATALOG


def summarize(folder):
    with (folder / "results.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    groups = defaultdict(list)
    details = []
    for row in rows:
        result = json.loads(
            (folder / f"{row['variant']}-{row['case_id']}.json").read_text(encoding="utf-8")
        )
        calls = [e for e in result["events"] if e["action"] == "tool"]
        valid = sum(e["tool"] in CATALOG for e in calls)
        params = 0
        for e in calls:
            try:
                CATALOG[e["tool"]][0].model_validate(e["arguments"])
                params += 1
            except (ValueError, KeyError):
                pass
        cited = result.get("diagnosis", {}).get("evidence_ids", [])
        detail = {
            **row,
            "tool_calls": len(calls),
            "whitelisted_calls": valid,
            "valid_parameters": params,
            "citations": len(cited),
            "existing_citations": sum(c in result["evidence"] for c in cited),
            "retrieval_calls": sum(e["tool"] == "search_docs" for e in calls),
            "orchestrator_fallback_calls": sum(
                e.get("source") == "mandatory_evidence_fallback" for e in calls
            ),
            "tool_failures": sum(not e["output"]["ok"] for e in calls),
            "semantic_citation_correctness": None,
            "hallucination_rate": None,
        }
        details.append(detail)
        groups[row["variant"]].append(detail)
    summary = {}
    for name, group in groups.items():
        latency = sorted(float(r["duration_ms"]) / 1000 for r in group)

        def ratio(a, b, group=group):
            denom = sum(r[b] for r in group)
            return sum(r[a] for r in group) / denom if denom else None

        pos = (len(latency) - 1) * 0.95
        lo = int(pos)
        p95 = latency[lo] + (latency[min(lo + 1, len(latency) - 1)] - latency[lo]) * (pos - lo)
        summary[name] = {
            "tasks": len(group),
            "completion_rate": sum(r["completed"] == "True" for r in group) / len(group),
            "category_hit_rate": sum(r["root_cause_hit"] == "True" for r in group) / len(group),
            "tool_whitelist_rate": ratio("whitelisted_calls", "tool_calls"),
            "parameter_schema_valid_rate": ratio("valid_parameters", "tool_calls"),
            "citation_existence_rate": ratio("existing_citations", "citations"),
            "retrieval_calls": sum(r["retrieval_calls"] for r in group),
            "orchestrator_fallback_calls": sum(r["orchestrator_fallback_calls"] for r in group),
            "mean_seconds": statistics.mean(latency),
            "p50_seconds": statistics.median(latency),
            "p95_seconds": p95,
            "total_tokens": sum(int(r["tokens"]) for r in group),
            "estimated_cny": sum(float(r["estimated_cny"]) for r in group),
        }
    output = {
        "metrics": summary,
        "cases": details,
        "limitations": [
            "Synthetic fixtures, four problem templates; variants are not independent production incidents.",
            "category_hit_rate measures category labels, not a proven root cause or repaired service.",
            "Whitelist/schema/existence rates are structural checks, NOT tool-choice or semantic-citation accuracy.",
            "Semantic citation correctness and hallucination rate are unscored, not zero; see manual review.",
            "RAG enabled means the tool is available; retrieval_calls reports whether the model actually used it.",
            "P95 is linear interpolation on a small sample; no statistical superiority claim.",
        ],
    }
    (folder / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    summarize(parser.parse_args().folder)
