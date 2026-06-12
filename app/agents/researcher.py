"""
Researcher agent — fetch evidence via tools.retrieve() (no LLM).

Phase 3: first real agent extracted from api.py's inline retrieve() call.
Orchestrator will call run_research(plan, query) after Planner produces a Plan.
"""

from __future__ import annotations

import time

import structlog

from app.schemas import EvidenceChunk, Plan
from app.tools import retrieve

log = structlog.get_logger()

DEFAULT_TOP_K = 5


def run_research(
    query: str,
    plan: Plan,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[EvidenceChunk], float]:
    """
    Run vector search using the Planner's filters.

    Args:
        query:  User question (same as ChatRequest.query for now)
        plan:   Planner output — ticker, filing_ids (future filter), need_retrieval
        top_k:  Max evidence chunks to return

    Returns:
        (evidence_chunks, latency_ms)
    """
    if not plan.need_retrieval:
        log.info("researcher_skipped", reason="plan.need_retrieval=False")
        return [], 0.0

    ticker = plan.ticker or "AAPL"
    t0 = time.perf_counter()
    chunks = retrieve(query, ticker=ticker, top_k=top_k)
    latency_ms = (time.perf_counter() - t0) * 1000

    log.info(
        "researcher_done",
        ticker=ticker,
        chunk_count=len(chunks),
        latency_ms=round(latency_ms, 1),
    )
    return chunks, latency_ms