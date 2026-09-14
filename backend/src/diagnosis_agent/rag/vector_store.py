"""Small-corpus vector database backed by SQLite; exact cosine scan, not ANN."""

import json
import sqlite3
from pathlib import Path

import numpy as np


def chunks(text: str, size: int = 300, overlap: int = 60):
    if size <= overlap or overlap < 0:
        raise ValueError("invalid_chunk_window")
    return [
        text[i : i + size]
        for i in range(0, len(text), size - overlap)
        if text[i : i + size].strip()
    ]


class VectorStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS vectors (id TEXT PRIMARY KEY, payload TEXT, vector BLOB)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")

    def replace(self, records, vectors, model_id):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM vectors")
            db.executemany(
                "INSERT INTO vectors VALUES (?,?,?)",
                [
                    (
                        doc["chunk_id"],
                        json.dumps(doc, ensure_ascii=False),
                        np.asarray(vec, dtype=np.float32).tobytes(),
                    )
                    for doc, vec in zip(records, vectors)
                ],
            )
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('model',?)", (model_id,))

    def search(self, vector, model_id, top_k=10):
        q = np.asarray(vector, dtype=np.float32)
        with sqlite3.connect(self.path) as db:
            model = db.execute("SELECT value FROM metadata WHERE key='model'").fetchone()
            if not model or model[0] != model_id:
                raise ValueError("embedding_model_mismatch")
            rows = db.execute("SELECT payload,vector FROM vectors").fetchall()
        results = []
        for payload, binary in rows:
            vec = np.frombuffer(binary, dtype=np.float32)
            score = float(
                np.dot(vec, q) / max(float(np.linalg.norm(vec) * np.linalg.norm(q)), 1e-9)
            )
            results.append({**json.loads(payload), "vector_score": score})
        return sorted(results, key=lambda d: -d["vector_score"])[:top_k]


class NeuralRetriever:
    def __init__(self, embedding_model, reranker_model, path):
        from sentence_transformers import CrossEncoder, SentenceTransformer

        self.model_id = embedding_model
        self.embedder = SentenceTransformer(embedding_model, device="cpu")
        self.reranker = CrossEncoder(reranker_model, device="cpu", max_length=512)
        self.store = VectorStore(path)

    def build(self, docs):
        records = [
            {**d, "chunk_id": f"{d['id']}-{i}", "text": text}
            for d in docs
            for i, text in enumerate(chunks(d["text"]))
        ]
        vecs = self.embedder.encode([d["text"] for d in records], normalize_embeddings=True)
        self.store.replace(records, vecs, self.model_id)
        return len(records)

    def search(self, query, top_k=3):
        vector = self.embedder.encode(query, normalize_embeddings=True)
        hits = self.store.search(vector, self.model_id, top_k=max(top_k, 10))
        if hits:
            scores = self.reranker.predict([(query, h["text"]) for h in hits])
            for h, s in zip(hits, scores):
                h["score"] = float(s)
            hits.sort(key=lambda h: -h["score"])
        return {
            "query": query,
            "backend": "neural_sqlite_exact_cosine_crossencoder",
            "hits": hits[:top_k],
            "empty": not hits,
        }
