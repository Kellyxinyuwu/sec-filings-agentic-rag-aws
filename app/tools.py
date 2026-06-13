"""
Phase 1 RAG tools — API 和 agents 只调这一层，不直接碰 store.py。

分层原因：
  store.py   = 底层：Postgres/OpenSearch、embed、SQL/k-NN
  tools.py   = 产品接口：返回 EvidenceChunk（JSON / Researcher 直接用）

Phase 4 切换检索后端：
  只改 store.search_similar() 内部路由（读 .env VECTOR_BACKEND）；
  本文件的 retrieve() 签名不变 → orchestrator / researcher 零改动。
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
    # store 返回 plain dict；这里统一转成 API schema，agents 不用关心 pgvector vs OpenSearch
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