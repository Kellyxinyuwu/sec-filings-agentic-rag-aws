import uuid

import structlog
from fastapi import APIRouter

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
    return {"status": "ok", "phase": "3"}


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(request: RetrieveRequest) -> RetrieveResponse:
    """Phase 1: vector search only — returns evidence chunks, no LLM answer."""
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
    )

    log.info("retrieve_done", trace_id=trace_id, chunk_count=len(chunks))
    return RetrieveResponse(query=request.query, chunks=chunks)


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Phase 3: multi-agent orchestrator (Planner → Researcher → Writer → Verifier)."""
    trace_id = str(uuid.uuid4())
    log.info("chat_request", trace_id=trace_id, query=request.query, ticker=request.ticker)
    return run_chat(request, trace_id=trace_id)
