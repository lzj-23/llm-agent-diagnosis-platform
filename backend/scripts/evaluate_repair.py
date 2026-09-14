"""Development challenge set for one-shot revision, not an independent benchmark."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from diagnosis_agent.agents.engine import Diagnosis, Engine
from diagnosis_agent.agents.model import ModelClient
from diagnosis_agent.agents.quality import audit_report

ROOT = Path(__file__).resolve().parents[2]


async def main(OUT):
    OUT.mkdir(parents=True, exist_ok=True)
    saved = json.loads(
        (ROOT / "evaluation-results/release-smoke/single-config-0.json").read_text(encoding="utf-8")
    )
    samples = [("observed-config-failure", saved["diagnosis"], saved["evidence"])]
    for name, text, evidence in [
        ("missing-logs", "没有异常日志，已排除OOM风险", {"logs": [], "metrics": "missing"}),
        (
            "contradictory",
            "平均显存很低，已排除显存不足",
            {"mean_memory_mib": 100, "logs": ["CUDA out of memory"]},
        ),
        ("unexecuted-action", "故障已修复", {"action": "read_only", "retest": "not_run"}),
        ("units", "将并发限制为4.2 QPS", {"observed_qps": 4.2, "concurrency": 16}),
    ]:
        samples.append(
            (
                name,
                {
                    "category": "unknown",
                    "conclusion": text,
                    "evidence_ids": ["challenge"],
                    "recommendations": [],
                    "verification": [],
                    "uncertainty": "尚未复测",
                },
                {"challenge": evidence},
            )
        )
    rows = []
    for name, raw, evidence in samples:
        model, events = ModelClient(), []

        async def invoke(role, messages, model=model):
            return await model.chat(messages)

        def event(role, action, events=events, **data):
            events.append({"role": role, "action": action, **data})

        original = Diagnosis.model_validate(raw)
        findings = audit_report(raw)
        revised, remaining = await Engine.repair_report(original, evidence, findings, invoke, event)
        row = {
            "id": name,
            "original": raw,
            "evidence": evidence,
            "findings": findings,
            "revised": revised.model_dump(),
            "remaining": remaining,
            "events": events,
            "usage": model.usage,
            "lint_pass": not remaining,
        }
        (OUT / f"{name}.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows.append({"id": name, "lint_pass": not remaining})
        print(name, not remaining, flush=True)
    source = ROOT / "backend/src/diagnosis_agent/agents/engine.py"
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": "one observed failure plus four authored development challenges; not held-out",
                "scope": "revision only; no new tool collection or physical experiments",
                "engine_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "rows": rows,
                "limitation": "lint pass is not semantic correctness; read each revised report",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evaluation-results/quality-repair-v2")
    asyncio.run(main(ROOT / parser.parse_args().output))
