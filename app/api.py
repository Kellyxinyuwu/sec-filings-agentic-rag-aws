import time
import uuid

import structlog
from fastapi import APIRouter

from app.llm import chat as llm_chat
from app.prompts import build_rag_prompt
from app.schemas import (
    AgentStep,
    ChatRequest,
    ChatResponse,
    Citation,
    EvidenceChunk,
    Plan,
    QueryIntent,
    RetrieveRequest,
    RetrieveResponse,
)
from app.tools import retrieve

router = APIRouter()
log = structlog.get_logger()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "2"}


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


def _chunks_to_citations(chunks: list[EvidenceChunk]) -> list[Citation]:
    return [
        Citation(
            chunk_id=c.chunk_id,
            filing_id=c.filing_id,
            section=c.section,
            excerpt=c.excerpt,
        )
        for c in chunks
    ]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Phase 2: real retrieve + Mantle grounded answer (via app.llm.chat)."""
    trace_id = str(uuid.uuid4())
    log.info("chat_request", trace_id=trace_id, query=request.query, ticker=request.ticker)

    plan = Plan(
        intent=QueryIntent.QA,
        need_retrieval=True,
        ticker=request.ticker,
        filing_ids=request.filing_ids,
        rationale="Phase 2: retrieve + Mantle writer (grounded on evidence)",
    )

    ticker = request.ticker or "AAPL"

    t0 = time.perf_counter()
    evidence = retrieve(request.query, ticker=ticker, top_k=5)
    researcher_ms = (time.perf_counter() - t0) * 1000

    system, user = build_rag_prompt(request.query, evidence)

    t1 = time.perf_counter()
    answer = llm_chat(system=system, user=user)
    writer_ms = (time.perf_counter() - t1) * 1000

    log.info(
        "chat_done",
        trace_id=trace_id,
        evidence_count=len(evidence),
        answer_chars=len(answer),
        writer_ms=round(writer_ms, 1),
    )

    return ChatResponse(
        answer=answer,
        citations=_chunks_to_citations(evidence),
        evidence=evidence,
        trace_id=trace_id,
        agent_steps=[
            AgentStep(step="planner", latency_ms=1.0),
            AgentStep(
                step="researcher",
                latency_ms=round(researcher_ms, 1),
                detail=f"{len(evidence)} chunks",
            ),
            AgentStep(
                step="writer",
                latency_ms=round(writer_ms, 1),
                detail="mantle",
            ),
            AgentStep(step="verifier", latency_ms=1.0, detail="mock pass"),
        ],
        plan=plan,
    )