"""
Tests for Verifier agent — verify_answer() (Phase 3 Step 4).

----------------------------------------------------------------------
测什么？
  - 合法 citation → pass
  - 伪造 chunk_id → fail + retry_hint
  - 有 evidence 但无 citation 且非拒答 → fail
  - REFUSE / 诚实拒答 → pass

Mock 策略：
  无 — 纯规则，直接传 answer + evidence。

怎么跑：
  pytest tests/test_verifier.py -q
  pytest -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

import pytest

from app.agents.verifier import verify_answer
from app.schemas import EvidenceChunk, Plan, QueryIntent

CHUNK = EvidenceChunk(
    chunk_id="AAPL-verify-001",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Risk text.",
    score=0.9,
)


def test_verifier_pass_valid_citation() -> None:
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    answer = "Supply chain risk is material [AAPL-verify-001]."
    result, ms = verify_answer(answer, plan, [CHUNK])

    assert result.passed is True
    assert ms >= 0.0
    assert result.retry_hint is None


def test_verifier_fail_invalid_citation() -> None:
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    answer = "Revenue was $100B [FAKE-CHUNK-ID]."
    result, _ = verify_answer(answer, plan, [CHUNK])

    assert result.passed is False
    assert result.retry_hint
    assert "FAKE-CHUNK-ID" in result.retry_hint


def test_verifier_fail_missing_citations() -> None:
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    answer = "Apple faces major supply chain and regulatory risks."
    result, _ = verify_answer(answer, plan, [CHUNK])

    assert result.passed is False
    assert "citation" in result.retry_hint.lower()


def test_verifier_pass_refuse_intent() -> None:
    plan = Plan(intent=QueryIntent.REFUSE, need_retrieval=False)
    answer = "Some answer without citations."
    result, _ = verify_answer(answer, plan, [])

    assert result.passed is True


def test_verifier_pass_honest_refusal() -> None:
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    answer = "I cannot answer from the provided filings."
    result, _ = verify_answer(answer, plan, [CHUNK])

    assert result.passed is True


def test_verifier_pass_empty_evidence() -> None:
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    answer = "No data available."
    result, _ = verify_answer(answer, plan, [])

    assert result.passed is True