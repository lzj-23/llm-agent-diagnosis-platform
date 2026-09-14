import asyncio
import json
import sqlite3
import time
from pathlib import Path

import httpx

from diagnosis_agent.config import get_settings


class ModelError(RuntimeError):
    pass


class Budget:
    """Reserve a conservative upper bound before each call; failed calls remain charged locally."""

    def __init__(self, path: Path, limit: float = 10):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.limit = path, limit
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY, reserved REAL)")
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, 0)")

    def reserve(self, amount: float):
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute("BEGIN IMMEDIATE")
            spent = db.execute("SELECT reserved FROM budget WHERE id=1").fetchone()[0]
            if spent + amount > self.limit:
                raise ModelError("budget_exhausted")
            db.execute("UPDATE budget SET reserved=reserved+? WHERE id=1", (amount,))


class ModelClient:
    def __init__(self, settings=None, transport=None):
        self.settings = settings or get_settings()
        self.transport = transport
        self.failures = 0
        self.open_until = 0
        self.usage = []
        self.budget = Budget(
            Path(self.settings.runtime_dir) / "budget.sqlite", self.settings.llm_budget_cny
        )

    async def chat(self, messages, tools=None):
        if time.monotonic() < self.open_until:
            raise ModelError("circuit_open")
        if not self.settings.llm_api_key:
            raise ModelError("missing_api_key")
        if not self.settings.llm_api_base or not self.settings.llm_model:
            raise ModelError("missing_model_configuration")
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "max_tokens": 1200,
            "temperature": 0,
            "enable_thinking": False,
        }
        if tools:
            payload["tools"] = tools
        # UTF-8 byte count is deliberately conservative; the ledger is a budget guard, not a bill.
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size > 60000:
            raise ModelError("context_budget_exceeded")
        input_price = self.settings.input_price_cny_per_million
        output_price = self.settings.output_price_cny_per_million
        reserved = (size * input_price + 1200 * output_price) / 1_000_000
        for attempt in range(3):
            self.budget.reserve(reserved)
            started = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=40, transport=self.transport) as client:
                    response = await client.post(
                        self.settings.llm_api_base.rstrip("/") + "/chat/completions",
                        headers={"Authorization": "Bearer " + self.settings.llm_api_key},
                        json=payload,
                    )
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.ReadTimeout("transient")
                if response.status_code != 200:
                    raise ModelError(f"model_http_{response.status_code}")
                data = response.json()
                usage = data.get("usage", {})
                actual = (
                    usage.get("prompt_tokens", 0) * input_price
                    + usage.get("completion_tokens", 0) * output_price
                ) / 1_000_000
                self.usage.append(
                    {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "estimated_cny": actual,
                        "duration_ms": (time.perf_counter() - started) * 1000,
                        "attempt": attempt + 1,
                    }
                )
                self.failures = 0
                return data["choices"][0]["message"]
            except (httpx.TimeoutException, httpx.NetworkError):
                self.failures += 1
                if attempt == 2:
                    self.open_until = time.monotonic() + 30
                    raise ModelError("model_timeout_or_rate_limit") from None
                await asyncio.sleep(0.2 * 2**attempt)
        raise ModelError("model_unavailable")
