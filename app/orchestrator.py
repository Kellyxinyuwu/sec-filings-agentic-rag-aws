"""
Agent orchestrator — Planner → Researcher → Writer → Verifier.

Phase 3 Step 5: single entry run_chat() for the multi-agent pipeline.
Step 6 wires api.py to call this instead of inline retrieve + llm.
"""

from __future__ import annotations

import uuid

import structlog

from app.agents.planner import run_planner
from app.agents.researcher import run_research
from app.agents.verifier import verify_answer
from app.agents.writer import run_writer
from app.config import settings
from app.schemas import (
    AgentStep,
    ChatRequest,
    ChatResponse,
    Citation,
    EvidenceChunk,
)

log = structlog.get_logger()

DEFAULT_TOP_K = 5

FAIL_CLOSED_ANSWER = (
    "I could not produce a fully cited answer from the provided filings. "
    "Please review the evidence excerpts below."
)


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


def run_chat(request: ChatRequest, *, trace_id: str | None = None) -> ChatResponse:
    """
    Run the full agent pipeline and return ChatResponse.

    Verifier failure triggers one Writer retry with verifier_feedback.
    Second failure → fail-closed answer (evidence still returned).
    """
    trace_id = trace_id or str(uuid.uuid4())
    log.info("orchestrator_start", trace_id=trace_id, query=request.query)

    plan, planner_ms = run_planner(request)

    evidence, researcher_ms = run_research(
        request.query,
        plan,
        top_k=DEFAULT_TOP_K,
    )

    answer, writer_ms = run_writer(request.query, plan, evidence)
    writer_detail = settings.llm_provider
    writer_retried = False

    verification, verifier_ms = verify_answer(answer, plan, evidence)

    if not verification.passed and verification.retry_hint:
        writer_retried = True
        retry_ms = 0.0
        answer, retry_ms = run_writer(
            request.query,
            plan,
            evidence,
            verifier_feedback=verification.retry_hint,
        )
        writer_ms += retry_ms
        writer_detail = f"{settings.llm_provider}, retry once"
        verification, verifier_ms = verify_answer(answer, plan, evidence)

    if not verification.passed:
        answer = FAIL_CLOSED_ANSWER
        verifier_detail = f"fail-closed: {verification.detail}"
    else:
        verifier_detail = verification.detail
        if writer_retried:
            verifier_detail = f"pass after retry: {verification.detail}"

    log.info(
        "orchestrator_done",
        trace_id=trace_id,
        intent=plan.intent.value,
        evidence_count=len(evidence),
        verifier_passed=verification.passed,
        writer_retried=writer_retried,
    )

    return ChatResponse(
        answer=answer,
        citations=_chunks_to_citations(evidence),
        evidence=evidence,
        trace_id=trace_id,
        agent_steps=[
            AgentStep(
                step="planner",
                latency_ms=round(planner_ms, 1),
                detail=plan.intent.value,
            ),
            AgentStep(
                step="researcher",
                latency_ms=round(researcher_ms, 1),
                detail=f"{len(evidence)} chunks",
            ),
            AgentStep(
                step="writer",
                latency_ms=round(writer_ms, 1),
                detail=writer_detail,
            ),
            AgentStep(
                step="verifier",
                latency_ms=round(verifier_ms, 1),
                detail=verifier_detail,
            ),
        ],
        plan=plan,
    )