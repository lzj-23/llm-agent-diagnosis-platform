"""Publish small reproducible measurements without local machine paths or generated text."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def summarize(before, after, output):
    samples = []
    for source in (before, after):
        data = source.read_bytes()
        raw = json.loads(data)
        samples.append(
            {
                "source_sha256": hashlib.sha256(data).hexdigest(),
                "context_tokens": raw["context_tokens"],
                "model": raw["model"],
                "backend": raw["backend"],
                "gpu_observation": raw.get("gpu_device_observation_after_load"),
                "server_slots": raw["server_slots"],
                "output_token_limit": raw["output_token_limit"],
                "timestamp": raw["generated_at"],
                "rows": [
                    {k: r[k] for k in ("label", "status", "e2e_seconds")} for r in raw["requests"]
                ],
            }
        )
        log = source.parent / "server.log"
        if log.exists() and raw.get("requested_gpu_layers"):
            data = log.read_bytes()
            text = data.decode("utf-8", errors="replace")
            samples[-1]["gpu_log_sha256"] = hashlib.sha256(data).hexdigest()
            samples[-1]["gpu_log_evidence"] = re.findall(
                r"offloaded \d+/\d+ layers to GPU|CUDA0 model buffer size =\s+[\d.]+ MiB", text
            )
    first = samples[0]["rows"][-1]
    second = samples[1]["rows"][-1]
    assert (first["label"], first["status"], second["status"]) == ("oversized-input", 400, 200)
    result = {
        "experiment": "Context-limit rejection and controlled local retest",
        "runs": samples,
        "verified": "Same oversized input rejected at 512 context, accepted at 2048 context.",
        "limitations": [
            "Small llama.cpp 0.8B only; inspect backend and separate GPU evidence; not vLLM/SGLang or production.",
            "One oversized request per configuration; not a reliability estimate.",
            "No TTFT, GPU utilization or memory peak measured.",
            "Latency samples are small, ordered and affected by warmup/cache.",
        ],
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.before, args.after, args.output)
