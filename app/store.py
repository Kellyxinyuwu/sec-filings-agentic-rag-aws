"""
Phase 1 数据层 — PostgreSQL + pgvector + 本地 embedding 模型

Step 4 在整条 RAG 链路里干什么？
---------------------------------
  10-K 原文 (Step 5 ingest)
       │
       ▼  chunk 文本列表
  embed_texts()  ──► 每段文字变成 384 个浮点数 (向量)
       │
       ▼
  insert_chunks() ──► 写入 Postgres 的 documents 表 (content + embedding + metadata)

  用户问题 "What are the risk factors?" (Step 6 retrieve)
       │
       ▼
  embed_query()  ──► 问题也变成同样长度的向量
       │
       ▼
  search_similar() ──► 在库里找「向量最接近」的 chunk → 当作证据 (EvidenceChunk)

为什么需要这个文件？
------------------
  - 把「连数据库、算向量、查相似度」集中在一处，ingest 和 API 不用重复写 SQL
  - 全项目用 settings.database_url / settings.embedding_model，不散落 os.getenv
  - 表结构在这里定义 (init_schema)，改字段不用重建 Docker 卷

对外主要函数:
  init_schema()     建表 (第一次 ingest 前调用)
  insert_chunks()   Step 5 ingest 写入
  search_similar()  Step 6 retrieve 查询
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extensions import connection as PgConnection

import structlog

from app.config import settings

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# all-MiniLM-L6-v2 输出固定 384 维向量。
# CREATE TABLE 里必须写 vector(384)，维度和模型不一致会 insert 失败。
EMBEDDING_DIM = 384

# 进程内只加载一次模型（几百 MB）。第一次 embed 会下载权重，之后复用。
_embedding_model = None

# 10-K 章节猜测规则：看 chunk 开头 800 字符是否像 "Item 1A" / "risk factors" 等。
# Phase 1 用简单正则即可；精确解析 HTML 可以以后再做。
_SECTION_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"item\s*1a\b", re.I), "Item 1A"),
    (re.compile(r"item\s*1\b", re.I), "Item 1"),
    (re.compile(r"item\s*7a\b", re.I), "Item 7A"),
    (re.compile(r"item\s*7\b", re.I), "Item 7"),
    (re.compile(r"item\s*8\b", re.I), "Item 8"),
    (re.compile(r"risk\s+factors", re.I), "Item 1A"),
]


# ---------------------------------------------------------------------------
# 数据库连接
# ---------------------------------------------------------------------------


def get_connection() -> PgConnection:
    """用 Step 3 的 settings.database_url 连接 Docker 里的 Postgres (localhost:5433)。"""
    return psycopg2.connect(settings.database_url)


# ---------------------------------------------------------------------------
# Embedding（文本 → 向量）
# ---------------------------------------------------------------------------


def _get_embedding_model():
    """
    懒加载 SentenceTransformer。

    为什么懒加载？
      - import store 时不会立刻下载模型，只有真正 embed 时才加载
      - pytest 测 API 时若不碰 store，不会拖慢启动
    """
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        log.info("loading_embedding_model", model=settings.embedding_model)
        _embedding_model = SentenceTransformer(settings.embedding_model)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    批量把文本变成向量（ingest 时用）。

    输入: ["Apple faces competition...", "The Company may..."]
    输出: [[0.12, -0.03, ...], [0.08, 0.01, ...]]  每个内层 list 长度 384

    重要: ingest 和 retrieve 必须用同一个模型，否则向量空间对不上，检索没意义。
    """
    if not texts:
        return []
    vectors = _get_embedding_model().encode(texts, show_progress_bar=False)
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    """把用户问题变成向量（retrieve 时用）。内部复用 embed_texts，保证模型一致。"""
    return embed_texts([query])[0]


# ---------------------------------------------------------------------------
# Metadata 辅助
# ---------------------------------------------------------------------------


def infer_section(text: str) -> str:
    """
    从 chunk 正文猜它属于 10-K 哪一节（Item 1A 风险因素、Item 7 MD&A 等）。

    只是启发式，猜错也没关系；目的是 citation 里能显示 section 字段。
    猜不到就返回 "Unknown"。
    """
    window = text[:800]
    for pattern, label in _SECTION_RULES:
        if pattern.search(window):
            return label
    return "Unknown"


# ---------------------------------------------------------------------------
# 建表
# ---------------------------------------------------------------------------


def init_schema(conn: PgConnection | None = None) -> None:
    """
    创建 pgvector 扩展 + documents 表（若已存在则跳过）。

    表一行 = 一个 chunk（一小段 10-K 原文 + 它的向量 + 出处信息）。
    字段和 app/schemas.py 里的 EvidenceChunk 对齐，方便后面 API 直接返回。

    conn 参数:
      - 不传: 自己开连接、建表、关闭（验证脚本用）
      - 传入: 在已有连接上建表（insert_chunks 里复用同一连接）
    """
    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    # 告诉 psycopg2 怎么读写 Postgres 的 vector 类型（否则 insert 向量会报错）
    register_vector(conn)

    cur = conn.cursor()
    # Docker init-db.sql 里已经 CREATE EXTENSION 过；这里再写一次也安全 (IF NOT EXISTS)
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS documents (
            chunk_id   TEXT PRIMARY KEY,           -- 唯一 ID，citation 引用用
            content    TEXT NOT NULL,              -- chunk 原文
            embedding  vector({EMBEDDING_DIM}),  -- pgvector 列，存 384 维向量
            ticker     TEXT NOT NULL,              -- 如 AAPL
            filing_id  TEXT NOT NULL,              -- SEC accession 号
            section    TEXT NOT NULL DEFAULT 'Unknown',  -- Item 1A 等
            source     TEXT                        -- 来源文件路径（调试用）
        )
        """
    )
    # 按 ticker 过滤时加速（retrieve 常带 ticker=AAPL）
    cur.execute(
        "CREATE INDEX IF NOT EXISTS documents_ticker_idx ON documents (ticker)"
    )
    conn.commit()
    cur.close()
    if own_conn:
        conn.close()


# ---------------------------------------------------------------------------
# 写入（ingest 路径）
# ---------------------------------------------------------------------------


def insert_chunks(
    chunks: list[str],
    *,
    ticker: str,
    filing_id: str,
    source: str,
    sections: list[str] | None = None,
    chunk_ids: list[str] | None = None,
) -> int:
    """
    把切好的文本块 embed 后写入数据库。

    Step 5 ingest_edgar.py 调用流程:
      1. 下载 10-K → 切成 chunks 列表
      2. insert_chunks(chunks, ticker="AAPL", filing_id="0000320193-...", source="...")
      3. 本函数内部: embed → INSERT

    返回写入的 chunk 数量。
    """
    if not chunks:
        return 0

    # 1) 文本 → 向量
    embeddings = embed_texts(chunks)

    # 2) 每块猜 section（也可由调用方传入 sections 覆盖）
    if sections is None:
        sections = [infer_section(c) for c in chunks]

    # 3) 稳定 ID：ingest 脚本用 AAPL-accession-00001 这种；没传则用随机 uuid
    if chunk_ids is None:
        chunk_ids = [uuid.uuid4().hex for _ in chunks]

    conn = get_connection()
    register_vector(conn)
    init_schema(conn)  # 确保表存在（用同一条连接，避免竞态）

    cur = conn.cursor()
    for chunk_id, content, embedding, section in zip(
        chunk_ids, chunks, embeddings, sections
    ):
        cur.execute(
            """
            INSERT INTO documents
                (chunk_id, content, embedding, ticker, filing_id, section, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (chunk_id) DO UPDATE SET
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                section = EXCLUDED.section,
                source = EXCLUDED.source
            """,
            (
                chunk_id,
                content,
                # pgvector 驱动需要 numpy array，不能直接传 Python list
                np.array(embedding, dtype=np.float32),
                ticker,
                filing_id,
                section,
                source,
            ),
        )
    conn.commit()
    cur.close()
    conn.close()
    return len(chunks)


# ---------------------------------------------------------------------------
# 检索（retrieve 路径）
# ---------------------------------------------------------------------------


def search_similar(
    query: str,
    *,
    ticker: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
  向量相似度搜索 — RAG 的「R」(Retrieval)。

  VECTOR_BACKEND=opensearch 时走 OpenSearch k-NN（Step 4+）；
  默认 local 仍用 pgvector（Phase 1–3 行为不变）。
    """
    from app.aws import use_opensearch

    if use_opensearch():
        from app.store_opensearch import search_similar_opensearch

        return search_similar_opensearch(query, ticker=ticker, top_k=top_k)

    return _search_similar_pgvector(query, ticker=ticker, top_k=top_k)


def _search_similar_pgvector(
    query: str,
    *,
    ticker: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
  pgvector 路径 — 余弦距离 <=>，score = 1 - distance。
    """
    # 问题也要 embed — 必须和入库时用同一模型
    query_embedding = embed_query(query)

    conn = get_connection()
    register_vector(conn)

    cur = conn.cursor()
    if ticker:
        # 常见路径：用户问了 AAPL，只在 AAPL 的 chunk 里搜
        cur.execute(
            """
            SELECT chunk_id, filing_id, ticker, section, content,
                   (1 - (embedding <=> %s::vector)) AS score
            FROM documents
            WHERE ticker = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (
                query_embedding,
                ticker,
                query_embedding,
                top_k,
            ),
        )
    else:
        # 不限 ticker：全库搜（Phase 1 demo 一般用上面带 ticker 的分支）
        cur.execute(
            """
            SELECT chunk_id, filing_id, ticker, section, content,
                   (1 - (embedding <=> %s::vector)) AS score
            FROM documents
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, query_embedding, top_k),
        )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    # 转成 plain dict，Step 6 tools.py 再包装成 EvidenceChunk
    return [
        {
            "chunk_id": row[0],
            "filing_id": row[1],
            "ticker": row[2],
            "section": row[3],
            "excerpt": row[4],  # DB 列名是 content，API schema 叫 excerpt
            "score": float(row[5]),
        }
        for row in rows
    ]
