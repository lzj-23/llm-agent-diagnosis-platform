from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Run(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    model: str
    device: str
    context_size: int = Field(gt=0)
    concurrency: int = Field(gt=0)
    prompt_profile: str = "fixed"
    max_tokens: int = Field(default=128, gt=0)
    metrics: dict[str, float | None]
    config: dict[str, Any] = Field(default_factory=dict)


class Log(StrictModel):
    timestamp: str
    level: Literal["INFO", "WARNING", "ERROR"]
    message: str = Field(max_length=4000)


class Case(StrictModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    description: str = Field(min_length=1, max_length=2000)
    synthetic: bool = True
    baseline: Run
    current: Run
    logs: list[Log] = Field(max_length=100)
    expected: str = "unknown"


class ToolResult(StrictModel):
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    retryable: bool = False


class CaseArgs(StrictModel):
    case_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")


class SearchArgs(StrictModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=10)


class ReportArgs(StrictModel):
    case_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    conclusion: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[str] = Field(max_length=30)
    recommendations: list[str] = Field(default_factory=list, max_length=10)
