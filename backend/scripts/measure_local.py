"""Opt-in, bounded local CPU experiment. Existing binaries/model files stay read-only."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


async def measure(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    command = [
        args.server,
        "-m",
        args.model,
        "-c",
        str(args.context),
        "-np",
        "1",
        "-ngl",
        str(args.gpu_layers),
        "-t",
        "4",
        "--host",
        "127.0.0.1",
        "--port",
        "18082",
        "--verbose",
    ]
    rows = []
    gpu_observation = None
    with (output / "server.log").open("w", encoding="utf-8") as log:
        process = await asyncio.to_thread(subprocess.Popen, command, stdout=log, stderr=log)
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:18082", timeout=90) as client:
                for _ in range(60):
                    try:
                        if (await client.get("/health")).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None:
                        raise RuntimeError("local server exited; inspect server.log")
                    await asyncio.sleep(1)
                else:
                    raise RuntimeError("local server readiness timeout")
                if args.gpu_layers:
                    gpu_observation = await asyncio.to_thread(
                        subprocess.check_output,
                        ["nvidia-smi", "--query-gpu=name,memory.used", "--format=csv,noheader"],
                        text=True,
                        timeout=10,
                    )

                async def request(label, prompt):
                    started = time.perf_counter()
                    response = await client.post(
                        "/completion",
                        json={
                            "prompt": prompt,
                            "n_predict": 32,
                            "temperature": 0,
                            "cache_prompt": False,
                            "stream": False,
                        },
                    )
                    elapsed = time.perf_counter() - started
                    body = response.json()
                    row = {
                        "label": label,
                        "status": response.status_code,
                        "e2e_seconds": elapsed,
                        "body": body,
                    }
                    rows.append(row)
                    return row

                prompt = "Explain in one sentence why inference requests can queue."
                await request("warmup", prompt)
                for i in range(3):
                    await request(f"serial-{i}", prompt)
                await asyncio.gather(*(request(f"concurrent-{i}", prompt) for i in range(3)))
                await request("oversized-input", "hello " * 1200)
        finally:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, timeout=5)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": Path(args.model).name,
        "backend": "llama.cpp, CPU, 4 threads"
        if args.gpu_layers == 0
        else "llama.cpp, CUDA offload requested, 4 CPU threads",
        "requested_gpu_layers": args.gpu_layers,
        "gpu_device_observation_after_load": gpu_observation,
        "gpu_observation_scope": "Device-wide sample after model load, not per-process peak or allocator memory.",
        "context_tokens": args.context,
        "server_slots": 1,
        "output_token_limit": 32,
        "streaming": False,
        "ttft": "not measured",
        "dataset_kind": "real controlled local requests, not production incidents",
        "limitations": "Three requests per condition, order/cache effects uncontrolled; no population P95 or causal claim.",
        "requests": rows,
    }
    target = output / "measurements.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "requests": len(rows),
                "statuses": [r["status"] for r in rows],
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--context", type=int, choices=[512, 2048], default=512)
    parser.add_argument("--gpu-layers", type=int, choices=[0, 99], default=0)
    asyncio.run(measure(parser.parse_args()))
