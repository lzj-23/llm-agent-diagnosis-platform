import json

import pytest

from diagnosis_agent.tools.service import benchmark_adapter


def test_adapter_preserves_conditions(tmp_path):
    source = tmp_path / "run.json"
    source.write_text(
        json.dumps(
            {
                "case": {
                    "case_id": "example",
                    "model_key": "q4",
                    "device": "gpu",
                    "context_size": 2048,
                    "concurrency": 4,
                    "prompt_profile": "short",
                },
                "protocol": {"max_tokens": 128},
                "summary": {"success_rate": 0.9},
                "resources": {"gpu_memory_peak_mib": 5000},
            }
        )
    )
    run = benchmark_adapter(source, tmp_path)
    assert run.concurrency == 4
    assert run.metrics["success_rate"] == 0.9
    assert run.metrics["ttft_p95_seconds"] is None
    with pytest.raises(ValueError, match="path_outside"):
        benchmark_adapter(source, tmp_path / "other")
