"""
Writer agent — grounded answer via prompts + llm.chat().

Phase 3: extracts Phase 2 api.py logic (build_rag_prompt → llm.chat).
REFUSE plans get a fixed message without calling the LLM.
"""

from __future__ import annotations

import time

import structlog

from app.llm import chat as llm_chat
from app.prompts import build_rag_prompt
from app.schemas import EvidenceChunk, Plan, QueryIntent

log = structlog.get_logger()

REFUSE_ANSWER = (
    "I cannot provide investment or trading advice. "
    "I can only help with factual questions about SEC public filings."
)


def run_writer(
    query: str,
    plan: Plan,
    evidence: list[EvidenceChunk],
    *,
    verifier_feedback: str | None = None,
) -> tuple[str, float]:
    """
    Generate answer from evidence (or fixed refuse text).

    Args:
        query:             User question
        plan:              Planner output (intent drives refuse short-circuit)
        evidence:          Chunks from Researcher (may be empty)
        verifier_feedback: Optional hint from Verifier on retry (Step 5)

    Returns:
        (answer, latency_ms)
    """
    t0 = time.perf_counter()

    if plan.intent == QueryIntent.REFUSE:
        latency_ms = (time.perf_counter() - t0) * 1000
        log.info("writer_refuse", intent="refuse", latency_ms=round(latency_ms, 3))
        return REFUSE_ANSWER, latency_ms

    system, user = build_rag_prompt(query, evidence)
    if verifier_feedback:
        user = (
            f"{user}\n\n"
            f"Verifier feedback (revise your answer):\n{verifier_feedback}"
        )

    answer = llm_chat(system=system, user=user)
    latency_ms = (time.perf_counter() - t0) * 1000

    log.info(
        "writer_done",
        intent=plan.intent.value,
        evidence_count=len(evidence),
        answer_chars=len(answer),
        latency_ms=round(latency_ms, 1),
    )
    return answer, latency_ms