"""
OpenSearch Serverless index schema — Phase 4 Step 3.

与 pgvector `documents` 表字段对齐，方便 Step 4 store 双写 / 切换：
  chunk_id, content, embedding, ticker, filing_id, section, source

向量维度须与 settings.embedding_dimensions（MiniLM = 384）一致。
"""

from __future__ import annotations

from typing import Any

from app.config import settings


def build_index_body() -> dict[str, Any]:
    """
    k-NN index mapping for OpenSearch Serverless VECTORSEARCH collection.

    NextGen collections: only dimension + space_type on the field — no engine/method
    (AWS picks config internally). Classic AOSS used method.hnsw + engine.faiss.

    space_type cosinesimil 与 pgvector 的 <=> 余弦距离语义一致。
    """
    dim = settings.embedding_dimensions
    return {
        "settings": {
            "index.knn": True,
        },
        "mappings": {
            "properties": {
                "chunk_id": {"type": "keyword"},
                "content": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "space_type": "cosinesimil",
                },
                "ticker": {"type": "keyword"},
                "filing_id": {"type": "keyword"},
                "section": {"type": "keyword"},
                "source": {"type": "keyword"},
            }
        },
    }


def index_exists(client: Any, index: str) -> bool:
    """opensearch-py client.indices.exists wrapper."""
    return bool(client.indices.exists(index=index))
