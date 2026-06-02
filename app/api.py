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
)

router = APIRouter()
log = structlog.get_logger()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "phase": "0"}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Mock chat — replaced by orchestrator in Phase 3."""
    trace_id = str(uuid.uuid4())
    log.info("chat_request", trace_id=trace_id, query=request.query, ticker=request.ticker)

    plan = Plan(
        intent=QueryIntent.QA,
        need_retrieval=True,
        ticker=request.ticker,
        filing_ids=request.filing_ids,
        rationale="Phase 0 mock planner",
    )

    mock_chunk = EvidenceChunk(
        chunk_id="mock-chunk-1",
        filing_id="mock-filing-1",
        ticker=request.ticker or "AAPL",
        section="Item 1A — Risk Factors",
        excerpt="[Mock] Example risk factor excerpt for development.",
        score=0.99,
    )

    return ChatResponse(
        answer=(
            "[Mock response] Connect ingest + Bedrock + orchestrator in later phases. "
            f"Your question: {request.query!r}"
        ),
        citations=[
            Citation(
                chunk_id=mock_chunk.chunk_id,
                filing_id=mock_chunk.filing_id,
                section=mock_chunk.section,
                excerpt=mock_chunk.excerpt,
            )
        ],
        evidence=[mock_chunk],
        trace_id=trace_id,
        agent_steps=[
            AgentStep(step="planner", latency_ms=1.0),
            AgentStep(step="researcher", latency_ms=2.0),
            AgentStep(step="writer", latency_ms=3.0),
            AgentStep(step="verifier", latency_ms=1.0, detail="mock pass"),
        ],
        plan=plan,
    )
