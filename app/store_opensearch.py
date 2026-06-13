"""
OpenSearch chunk 存储 — Phase 4 Step 4 写、Step 5 ingest 灌数据、Step 6 检索读。

和 pgvector 的分工：
  ingest：ingest_edgar.py 可选 bulk 写入本模块（与 local 并行，embed 只算一次）
  retrieve：仅当 .env VECTOR_BACKEND=opensearch 时，store.search_similar() 调本文件

index mapping 见 opensearch_schema.py（384 维 knn_vector，NextGen 无 engine 字段）。
"""

from __future__ import annotations

from typing import Any

import structlog

from app.aws import get_opensearch_client
from app.config import settings

log = structlog.get_logger()


def _index_name() -> str:
    # 默认 sec-chunks；可在 .env OPENSEARCH_INDEX 覆盖
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
    Bulk index chunks into OpenSearch（ingest Step 5 调用）。

    - chunk_id 作 document _id → 重跑 ingest 是 upsert，不会 duplicate
    - embeddings 可由 ingest 预先传入（与 pgvector 共用同一次 MiniLM 计算）
    - 返回写入条数（= len(chunks)）
    """
    if not chunks:
        return 0

    import uuid

    from app.store import embed_texts, infer_section

    if embeddings is None:
        embeddings = embed_texts(chunks)  # 单独调用本函数时才内部 embed
    if sections is None:
        sections = [infer_section(c) for c in chunks]
    if chunk_ids is None:
        chunk_ids = [uuid.uuid4().hex for _ in chunks]

    ticker_u = ticker.upper()
    index = _index_name()
    client = get_opensearch_client()

    # bulk API 格式：一行 action + 一行 document，交替出现
    body: list[dict[str, Any]] = []
    for chunk_id, content, embedding, section in zip(
        chunk_ids, chunks, embeddings, sections
    ):
        body.append({"index": {"_index": index, "_id": chunk_id}})
        body.append(
            {
                "chunk_id": chunk_id,
                "content": content,
                "embedding": embedding,  # 384 维，须与 index mapping 一致
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
    k-NN 向量检索（Step 6 VECTOR_BACKEND=opensearch 时由 store.search_similar 调用）。

    - query 先 embed_query（须与 ingest 同一模型 MiniLM）
    - 可选 ticker filter：只在某公司 filing 里搜
    - 返回 dict 形状与 pgvector 路径一致，tools.py 才能统一包装 EvidenceChunk

    注意：OpenSearch 的 score 与 pgvector 的 (1 - distance) 尺度不同，chunk_id 可比。
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
        # 与 pgvector WHERE ticker = %s 等价
        knn_query["filter"] = {"term": {"ticker": ticker.upper()}}

    body = {
        "size": top_k,
        "query": {"knn": {"embedding": knn_query}},  # embedding = mapping 里的字段名
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
