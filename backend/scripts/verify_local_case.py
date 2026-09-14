"""Import measured local context rejection, then diagnose it over real MCP/model API."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from statistics import mean

from diagnosis_agent.agents.engine import Engine
from diagnosis_agent.config import get_settings
from diagnosis_agent.tools.contracts import Case, Log, Run


async def verify(source, output):
    raw_bytes = source.read_bytes()
    raw = json.loads(raw_bytes)
    rows = raw["requests"]
    serial = [r for r in rows if r["label"].startswith("serial-")]
    failure = next(r for r in rows if r["label"] == "oversized-input")
    assert failure["status"] == 400
    baseline = Run(
        id="local-serial",
        model=raw["model"],
        device="CPU, 4 threads",
        context_size=512,
        concurrency=1,
        max_tokens=32,
        prompt_profile="short-11-tokens",
        metrics={"e2e_mean_seconds": mean(r["e2e_seconds"] for r in serial), "success_rate": 1.0},
        config={"server_slots": 1},
    )
    current = baseline.model_copy(
        update={
            "id": "local-oversized",
            "prompt_profile": "oversized-1201-tokens",
            "metrics": {"e2e_mean_seconds": failure["e2e_seconds"], "success_rate": 0.0},
        }
    )
    case = Case(
        id="measured-context-20260914",
        synthetic=False,
        baseline=baseline,
        current=current,
        description="本机 llama.cpp CPU 实验：短请求成功，长请求返回400；解释错误原因，不推断GPU OOM。",
        logs=[
            Log(
                timestamp=raw["generated_at"],
                level="ERROR",
                message=failure["body"]["error"]["message"],
            )
        ],
    )
    cases = Path(get_settings().runtime_dir) / "cases"
    cases.mkdir(parents=True, exist_ok=True)
    target = cases / (case.id + ".json")
    if target.exists():
        raise FileExistsError(target.name)
    target.write_text(case.model_dump_json(indent=2), encoding="utf-8")
    output.mkdir(parents=True, exist_ok=False)
    (output / "case.json").write_text(case.model_dump_json(indent=2), encoding="utf-8")
    provenance = {
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "kind": raw["dataset_kind"],
        "limitations": raw["limitations"],
        "rows": [{k: r[k] for k in ("label", "status", "e2e_seconds")} for r in rows],
        "error": failure["body"]["error"],
        "timestamp": raw["generated_at"],
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    result = await Engine().run(case.description, case.id)
    (output / "diagnosis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "category": result.get("diagnosis", {}).get("category"),
                "error": result.get("error"),
                "quality_issues": result.get("quality_issues", []),
            }
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    asyncio.run(verify(a.source, a.output))
