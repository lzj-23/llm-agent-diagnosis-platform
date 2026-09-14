import numpy as np
import pytest

from diagnosis_agent.rag.vector_store import VectorStore, chunks


def test_persistent_cosine_search(tmp_path):
    path = tmp_path / "vectors.sqlite"
    s = VectorStore(path)
    s.replace(
        [{"chunk_id": "a", "text": "first"}, {"chunk_id": "b", "text": "second"}],
        [[1, 0], [0, 1]],
        "model-v1",
    )
    result = VectorStore(path).search(np.array([0, 1]), "model-v1", 1)
    assert result[0]["chunk_id"] == "b"
    with pytest.raises(ValueError, match="embedding_model_mismatch"):
        s.search([0, 1], "model-v2")


def test_chunk_overlap():
    assert chunks("abcdefgh", 4, 1) == ["abcd", "defg", "gh"]
    with pytest.raises(ValueError):
        chunks("a", 3, 3)
