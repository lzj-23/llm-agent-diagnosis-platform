from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "llm-agent-diagnosis-platform"
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    project_root: str = str(Path(__file__).resolve().parents[3])
    runtime_dir: str = str(Path(__file__).resolve().parents[3] / "runtime")
    llm_budget_cny: float = Field(default=10.0, gt=0, allow_inf_nan=False)
    input_price_cny_per_million: float = Field(default=0.8, ge=0, allow_inf_nan=False)
    output_price_cny_per_million: float = Field(default=2.7, ge=0, allow_inf_nan=False)
    rag_backend: str = "lexical"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    web_api_key: str = ""
    worker_count: int = 2

    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    rag_result_root: str | None = None
    benchmark_result_root: str | None = None
    database_url: str | None = None
    redis_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
