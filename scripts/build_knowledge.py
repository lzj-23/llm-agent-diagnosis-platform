"""Build and smoke-test a CPU embedding + CrossEncoder index from approved runbooks."""

import json
import os
from pathlib import Path

from diagnosis_agent.config import get_settings
from diagnosis_agent.rag.knowledge import DOCS
from diagnosis_agent.rag.vector_store import NeuralRetriever

s = get_settings()
retriever = NeuralRetriever(
    os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
    os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-base"),
    Path(s.runtime_dir) / "knowledge.sqlite",
)
count = retriever.build(DOCS)
result = retriever.search("CUDA out of memory 显存不足如何排查？")
out = Path("evaluation-results/rag-smoke.json")
out.parent.mkdir(exist_ok=True, parents=True)
out.write_text(
    json.dumps({"chunks": count, "result": result}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(
    {"chunks": count, "top_hit": result["hits"][0]["id"], "backend": result["backend"]}
)
