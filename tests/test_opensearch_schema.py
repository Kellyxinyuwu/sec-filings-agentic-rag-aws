"""Tests for app/opensearch_schema.py — no AWS."""

from unittest.mock import MagicMock

from app.config import settings
from app.opensearch_schema import build_index_body, index_exists


def test_build_index_body_dimension_matches_settings() -> None:
    body = build_index_body()
    emb = body["mappings"]["properties"]["embedding"]
    assert emb["dimension"] == settings.embedding_dimensions
    assert emb["type"] == "knn_vector"
    assert emb["space_type"] == "cosinesimil"
    assert "engine" not in emb
    assert "method" not in emb


def test_build_index_body_has_pgvector_aligned_fields() -> None:
    props = build_index_body()["mappings"]["properties"]
    for field in ("chunk_id", "content", "embedding", "ticker", "filing_id", "section", "source"):
        assert field in props


def test_index_exists_true() -> None:
    client = MagicMock()
    client.indices.exists.return_value = True
    assert index_exists(client, "sec-chunks") is True
    client.indices.exists.assert_called_once_with(index="sec-chunks")
