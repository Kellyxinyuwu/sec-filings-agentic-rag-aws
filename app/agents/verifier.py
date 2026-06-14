"""
Verifier agent — citation checks on Writer output (rules-based MVP, no LLM).

Phase 3: fail-closed when citations are missing or point outside evidence.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import structlog

from app.schemas import EvidenceChunk, Plan, QueryIntent

log = structlog.get_logger()

# Matches [AAPL-0000320193-25-000079-00217] style citations in answers.
_CITATION_RE = re.compile(r"\[([A-Za-z0-9_-]+)\]")

# Writer honest-refusal phrases (aligned with prompts.py grounding).
_REFUSAL_PHRASES: tuple[str, ...] = (
    "cannot answer from the provided filings",
    "do not state",
    "not state",
    "insufficient",
    "no evidence",
)


@dataclass(frozen=True)
class VerifierResult:
  """Outcome of verify_answer — consumed by orchestrator (Step 5)."""

  passed: bool
  detail: str
  retry_hint: str | None = None


def _extract_citations(answer: str) -> list[str]:
    return _CITATION_RE.findall(answer)


def _looks_like_honest_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(p in lower for p in _REFUSAL_PHRASES)


def verify_answer(
    answer: str,
    plan: Plan,
    evidence: list[EvidenceChunk],
) -> tuple[VerifierResult, float]:
    """
    Check grounded citations and basic fail-closed rules.

    Returns:
        (VerifierResult, latency_ms)
    """
    t0 = time.perf_counter()

    if plan.intent == QueryIntent.REFUSE:
        result = VerifierResult(
            passed=True,
            detail="refuse intent — fixed answer, citation check skipped",
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        log.info("verifier_done", passed=True, detail=result.detail)
        return result, latency_ms

    valid_ids = {c.chunk_id for c in evidence}
    cited = _extract_citations(answer)
    invalid = [cid for cid in cited if cid not in valid_ids]

    if invalid:
        hint = (
            "Remove or fix invalid chunk_id citations not in evidence: "
            + ", ".join(invalid)
            + ". Only cite chunk_ids from the evidence blocks."
        )
        result = VerifierResult(
            passed=False,
            detail=f"invalid citations: {invalid}",
            retry_hint=hint,
        )
    elif evidence and not cited and not _looks_like_honest_refusal(answer):
        hint = (
            "Answer makes claims but has no [chunk_id] citations. "
            "Cite evidence for each key claim, or state you cannot answer from the filings."
        )
        result = VerifierResult(
            passed=False,
            detail="missing citations despite non-empty evidence",
            retry_hint=hint,
        )
    else:
        detail = (
            "citations ok"
            if cited
            else "no citations required (empty evidence or honest refusal)"
        )
        result = VerifierResult(passed=True, detail=detail)

    latency_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "verifier_done",
        passed=result.passed,
        cited_count=len(cited),
        detail=result.detail,
        latency_ms=round(latency_ms, 3),
    )
    return result, latency_ms