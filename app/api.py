import uuid

import structlog
from fastapi import APIRouter

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
    return {"status": "ok", "phase": "1"}


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
    """Mock answer; evidence from real retrieve() when DB has data (Phase 1)."""
    trace_id = str(uuid.uuid4())
    log.info("chat_request", trace_id=trace_id, query=request.query, ticker=request.ticker)

    plan = Plan(
        intent=QueryIntent.QA,
        need_retrieval=True,
        ticker=request.ticker,
        filing_ids=request.filing_ids,
        rationale="Phase 1: real retrieve, mock writer",
    )

    ticker = request.ticker or "AAPL"
    evidence = retrieve(request.query, ticker=ticker, top_k=5)

    # Fallback if DB empty (e.g. fresh clone before ingest)
    if not evidence:
        evidence = [
            EvidenceChunk(
                chunk_id="mock-chunk-1",
                filing_id="mock-filing-1",
                ticker=ticker,
                section="Item 1A — Risk Factors",
                excerpt="[Mock] No chunks in DB — run ingest_edgar.py first.",
                score=0.0,
            )
        ]

    return ChatResponse(
        answer=(
            "[Mock response] Phase 2 will generate answers with Mantle/Bedrock. "
            f"Your question: {request.query!r}"
        ),
        citations=_chunks_to_citations(evidence),
        evidence=evidence,
        trace_id=trace_id,
        agent_steps=[
            AgentStep(step="planner", latency_ms=1.0),
            AgentStep(step="researcher", latency_ms=2.0, detail=f"{len(evidence)} chunks"),
            AgentStep(step="writer", latency_ms=3.0, detail="mock"),
            AgentStep(step="verifier", latency_ms=1.0, detail="mock pass"),
        ],
        plan=plan,
    )