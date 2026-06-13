"""
OpenSearch chunk storage — Phase 4 Step 4.

Bulk upsert + k-NN search against index mapping in opensearch_schema.py.
Called from store.py when VECTOR_BACKEND=opensearch (Step 6) or ingest dual-write (Step 5).
"""

from __future__ import annotations

from typing import Any

import structlog

from app.aws import get_opensearch_client
from app.config import settings

log = structlog.get_logger()


def _index_name() -> str:
    return settings.opensearch_index.strip() or "sec-chunks"


def upsert_chunks_opensearch(
    chunks: list[str],
    *,
    ticker: str,
    filing_id: str,
    source: str,
    sections: list[str] | None = None,
    chunk_ids: list[str] | None = None,
    embeddings: list[list[float]] | None = None,
) -> int:
    """
    Embed chunks and bulk-index into OpenSearch (same metadata shape as pgvector).

    Uses chunk_id as document _id so re-ingest is upsert-safe.
    """
    if not chunks:
        return 0

    import uuid

    from app.store import embed_texts, infer_section

    if embeddings is None:
        embeddings = embed_texts(chunks)
    if sections is None:
        sections = [infer_section(c) for c in chunks]
    if chunk_ids is None:
        chunk_ids = [uuid.uuid4().hex for _ in chunks]

    ticker_u = ticker.upper()
    index = _index_name()
    client = get_opensearch_client()

    body: list[dict[str, Any]] = []
    for chunk_id, content, embedding, section in zip(
        chunk_ids, chunks, embeddings, sections
    ):
        body.append({"index": {"_index": index, "_id": chunk_id}})
        body.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "embedding": embedding,
                "ticker": ticker_u,
                "filing_id": filing_id,
                "section": section,
                "source": source,
            }
        )

    log.info(
        "opensearch_bulk_upsert",
        index=index,
        ticker=ticker_u,
        filing_id=filing_id,
        chunks=len(chunks),
    )
    response = client.bulk(body=body)
    if response.get("errors"):
        errors = [
            item
            for item in response.get("items", [])
            if "error" in item.get("index", {})
        ]
        log.error("opensearch_bulk_errors", count=len(errors), sample=errors[:3])
        raise RuntimeError(f"OpenSearch bulk upsert failed ({len(errors)} errors)")

    return len(chunks)


def search_similar_opensearch(
    query: str,
    *,
    ticker: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    k-NN search on embedding field; optional ticker filter.

    Returns same dict shape as store.search_similar (pgvector path).
    """
    from app.store import embed_query

    query_embedding = embed_query(query)
    index = _index_name()
    client = get_opensearch_client()

    knn_query: dict[str, Any] = {
        "vector": query_embedding,
        "k": top_k,
    }
    if ticker:
        knn_query["filter"] = {"term": {"ticker": ticker.upper()}}

    body = {
        "size": top_k,
        "query": {"knn": {"embedding": knn_query}},
    }

    log.debug("opensearch_knn_search", index=index, ticker=ticker, top_k=top_k)
    response = client.search(index=index, body=body)

    rows: list[dict[str, Any]] = []
    for hit in response.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        rows.append(
            {
                "chunk_id": src.get("chunk_id", hit.get("_id", "")),
                "filing_id": src.get("filing_id", ""),
                "ticker": src.get("ticker", ""),
                "section": src.get("section", "Unknown"),
                "excerpt": src.get("content", ""),
                "score": float(hit.get("_score", 0.0)),
            }
        )
    return rows
