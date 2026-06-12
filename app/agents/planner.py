"""
Planner agent — produce a Plan from ChatRequest (rules-based MVP, no LLM).

Phase 3: replaces the hard-coded Plan in api.py.
Orchestrator calls run_planner(request) before Researcher.

MVP rules:
  - Investment / trading advice → QueryIntent.REFUSE, skip retrieval
  - Summarize / diff keywords   → matching intent, still retrieve
  - Default                     → QueryIntent.QA, need_retrieval=True
"""

from __future__ import annotations

import re
import time

import structlog

from app.schemas import ChatRequest, Plan, QueryIntent

log = structlog.get_logger()

# Case-insensitive substring match (lowercased query).
REFUSE_PATTERNS: tuple[str, ...] = (
    "should i buy",
    "should i sell",
    "buy or sell",
    "investment advice",
    "price target",
    "recommend buying",
    "recommend selling",
    "is it a good investment",
    "will the stock go up",
    "will the stock go down",
)

SUMMARIZE_PATTERNS: tuple[str, ...] = (
    "summarize",
    "summary of",
    "give me a summary",
    "brief overview of the filing",
)

DIFF_PATTERNS: tuple[str, ...] = (
    "compare",
    "difference between",
    " vs ",
    " versus ",
    "year over year",
    "yoy",
)

# Whole-word buy/sell (avoid matching "buyback" in filing excerpts if query is long — query is short)
_BUY_SELL_RE = re.compile(r"\b(buy|sell)\b", re.IGNORECASE)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(p in text for p in patterns)


def _is_refuse_query(query: str) -> bool:
    q = query.lower().strip()
    if _matches_any(q, REFUSE_PATTERNS):
        return True
    return _BUY_SELL_RE.search(q) is not None


def run_planner(request: ChatRequest) -> tuple[Plan, float]:
    """
    Build execution plan from user request.

    Returns:
        (plan, latency_ms)
    """
    t0 = time.perf_counter()
    query = request.query.strip()

    if _is_refuse_query(query):
        plan = Plan(
            intent=QueryIntent.REFUSE,
            need_retrieval=False,
            ticker=request.ticker,
            filing_ids=list(request.filing_ids),
            rationale="Planner: investment/trading advice — refuse without retrieval",
        )
    elif _matches_any(query.lower(), DIFF_PATTERNS):
        plan = Plan(
            intent=QueryIntent.DIFF,
            need_retrieval=True,
            ticker=request.ticker,
            filing_ids=list(request.filing_ids),
            rationale="Planner: diff/compare intent — retrieve (MVP: same pipeline as QA)",
        )
    elif _matches_any(query.lower(), SUMMARIZE_PATTERNS):
        plan = Plan(
            intent=QueryIntent.SUMMARIZE,
            need_retrieval=True,
            ticker=request.ticker,
            filing_ids=list(request.filing_ids),
            rationale="Planner: summarize intent — retrieve then write",
        )
    else:
        plan = Plan(
            intent=QueryIntent.QA,
            need_retrieval=True,
            ticker=request.ticker,
            filing_ids=list(request.filing_ids),
            rationale="Planner: QA — retrieve SEC evidence then grounded answer",
        )

    latency_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "planner_done",
        intent=plan.intent.value,
        need_retrieval=plan.need_retrieval,
        ticker=plan.ticker,
        latency_ms=round(latency_ms, 3),
    )
    return plan, latency_ms