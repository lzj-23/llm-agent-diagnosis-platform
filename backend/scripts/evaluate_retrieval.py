"""Small authored relevance check; not an independent retrieval benchmark."""

import argparse
import hashlib
import json
import time
from pathlib import Path

from diagnosis_agent.rag.knowledge import DOCS, search
from diagnosis_agent.rag.vector_store import NeuralRetriever

QUERIES = [
    ("vLLM chunked prefill如何平衡首字延迟与逐token延迟", "doc-vllm-prefill"),
    ("vLLM tensor parallel分片权重后为什么不一定更快", "doc-vllm-parallel"),
    ("empty_cache能否释放仍由张量使用的显存", "doc-torch-allocated"),
    ("max_split_size_mb适用于哪个分配器，如何确认碎片", "doc-torch-fragmentation"),
    ("SGLang在prefill阶段OOM应检查哪项参数", "doc-sglang-prefill"),
    ("SGLang降低mem-fraction-static有什么代价", "doc-sglang-memory"),
    ("SGLang排队但token usage低如何排查", "doc-sglang-queue"),
]


def evaluate(args):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    retriever = NeuralRetriever(
        args.embedding_model, args.reranker_model, str(output / "index.sqlite")
    )
    chunks = retriever.build(DOCS)
    rows = []
    for name, searcher in [("lexical", search), ("neural", retriever.search)]:
        for query, relevant in QUERIES:
            start = time.perf_counter()
            result = searcher(query, top_k=3)
            hits = [h["id"] for h in result["hits"]]
            rank = hits.index(relevant) + 1 if relevant in hits else None
            rows.append(
                {
                    "backend": name,
                    "query": query,
                    "relevant": relevant,
                    "hits": hits,
                    "reciprocal_rank_at_3": 1 / rank if rank else 0,
                    "duration_ms": (time.perf_counter() - start) * 1000,
                }
            )
    summary = {}
    for name in ("lexical", "neural"):
        group = [r for r in rows if r["backend"] == name]
        summary[name] = {
            "queries": len(group),
            "recall_at_3": sum(r["reciprocal_rank_at_3"] > 0 for r in group) / len(group),
            "mrr_at_3": sum(r["reciprocal_rank_at_3"] for r in group) / len(group),
        }
    manifest = {
        "documents": len(DOCS),
        "chunks": chunks,
        "corpus_sha256": hashlib.sha256(
            json.dumps(DOCS, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest(),
        "limitation": "Seven queries authored from the same corpus; not held out and not production retrieval quality.",
        "models": ["BAAI/bge-small-zh-v1.5", "BAAI/bge-reranker-base"],
        "summary": summary,
    }
    (output / "results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-model", required=True)
    parser.add_argument("--reranker-model", required=True)
    parser.add_argument("--output", required=True)
    evaluate(parser.parse_args())
