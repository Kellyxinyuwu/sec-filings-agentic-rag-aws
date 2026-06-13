"""
FastAPI 路由 — /health、/retrieve、/chat

调用链（Phase 4 Step 6 检索切换）：
  POST /retrieve  →  tools.retrieve()  →  store.search_similar()
                                              ├─ local      → pgvector
                                              └─ opensearch → AWS k-NN

  POST /chat  →  orchestrator  →  Researcher 也走 tools.retrieve()，所以改 .env
  的 VECTOR_BACKEND 即可切换整条 RAG 检索，不用改 agent 代码。

注意：settings 在 uvicorn 启动时加载；改 .env 后必须重启 API。
"""

import uuid

import structlog
from fastapi import APIRouter

from app.aws import vector_backend
from app.orchestrator import run_chat
from app.schemas import (
    ChatRequest,
    ChatResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from app.tools import retrieve

router = APIRouter()
log = structlog.get_logger()


@router.get("/health")
def health() -> dict[str, str]:
    # phase "4" = AWS 数据面（S3 + OpenSearch）已接线；vector_backend 显示当前检索走哪
    return {"status": "ok", "phase": "4", "vector_backend": vector_backend()}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(request: RetrieveRequest) -> RetrieveResponse:
    """Phase 1: 纯向量检索，不调 LLM。backend 由 VECTOR_BACKEND 决定（见 store.search_similar）。"""
    trace_id = str(uuid.uuid4())
    log.info(
        "retrieve_request",
        trace_id=trace_id,
        query=request.query,
        ticker=request.ticker,
        top_k=request.top_k,
    )

    chunks = retrieve(
        request.query,
        ticker=request.ticker,
        top_k=request.top_k,
    )  # 不直接调 store — 统一走 tools 层，agents 与 API 共用

    log.info("retrieve_done", trace_id=trace_id, chunk_count=len(chunks))
    return RetrieveResponse(query=request.query, chunks=chunks)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Phase 3: multi-agent orchestrator (Planner → Researcher → Writer → Verifier)."""
    trace_id = str(uuid.uuid4())
    log.info("chat_request", trace_id=trace_id, query=request.query, ticker=request.ticker)
    return run_chat(request, trace_id=trace_id)
