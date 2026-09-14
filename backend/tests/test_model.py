import asyncio

import httpx
import pytest

from diagnosis_agent.agents.model import Budget, ModelClient, ModelError
from diagnosis_agent.config import Settings


def test_persistent_budget(tmp_path):
    path = tmp_path / "budget.sqlite"
    Budget(path, 1).reserve(0.7)
    with pytest.raises(ModelError, match="budget_exhausted"):
        Budget(path, 1).reserve(0.4)


def test_transient_retry(tmp_path):
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "OK"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
            },
        )

    client = ModelClient(
        Settings(
            runtime_dir=str(tmp_path),
            llm_api_key="test",
            llm_api_base="https://example.test",
            llm_model="test",
        ),
        httpx.MockTransport(handler),
    )
    assert asyncio.run(client.chat([{"role": "user", "content": "test"}]))["content"] == "OK"
    assert len(attempts) == 2


def test_auth_not_retried(tmp_path):
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(401)

    client = ModelClient(
        Settings(
            runtime_dir=str(tmp_path),
            llm_api_key="test",
            llm_api_base="https://example.test",
            llm_model="test",
            _env_file=None,
        ),
        httpx.MockTransport(handler),
    )
    with pytest.raises(ModelError, match="model_http_401"):
        asyncio.run(client.chat([]))
    assert len(attempts) == 1


@pytest.mark.parametrize("recover", [True, False])
def test_truncation_retries_once_and_records_both_costs(tmp_path, recover):
    attempts = []

    def handler(request):
        attempts.append(1)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop" if recover and len(attempts) == 2 else "length",
                        "message": {"role": "assistant", "content": "{}"},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 1200},
            },
        )

    client = ModelClient(
        Settings(
            runtime_dir=str(tmp_path),
            llm_api_key="test",
            llm_api_base="https://example.test",
            llm_model="test",
            _env_file=None,
        ),
        httpx.MockTransport(handler),
    )
    if recover:
        assert asyncio.run(client.chat([]))["content"] == "{}"
    else:
        with pytest.raises(ModelError, match="model_output_truncated"):
            asyncio.run(client.chat([]))
    assert len(attempts) == len(client.usage) == 2
