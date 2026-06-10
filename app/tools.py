"""
Phase 1 RAG tools — API and agents call this layer, not store.py directly.

Why a separate file?
  - store.py  = database + vectors (low level)
  - tools.py  = product/agent interface (EvidenceChunk)
  - Phase 4 switch to OpenSearch: change store, keep tools.retrieve() signature
"""

from __future__ import annotations

from app.schemas import EvidenceChunk
from app.store import search_similar


def retrieve(
    query: str,
    *,
    ticker: str | None = None,
    top_k: int = 5,
) -> list[EvidenceChunk]:
    """
    Vector search over ingested SEC chunks.

    Args:
        query:  e.g. "What are the main risk factors?"
        ticker: e.g. "AAPL" — strongly recommended in Phase 1 (only one ticker ingested)
        top_k:  number of evidence chunks to return

    Returns:
        list[EvidenceChunk] for JSON API or Researcher agent (Phase 3)
    """
    rows = search_similar(query, ticker=ticker, top_k=top_k)

    return [
        EvidenceChunk(
            chunk_id=row["chunk_id"],
            filing_id=row["filing_id"],
            ticker=row["ticker"],
            section=row["section"],
            excerpt=row["excerpt"],
            score=row["score"],
        )
        for row in rows
    ]