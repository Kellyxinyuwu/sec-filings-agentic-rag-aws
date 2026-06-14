"""
Tests for Planner agent — run_planner() (Phase 3 Step 2).

----------------------------------------------------------------------
测什么？
  - 正常 QA → intent=qa, need_retrieval=True
  - 投资建议 → intent=refuse, need_retrieval=False
  - summarize / diff 关键词 → 对应 intent
  - ticker、filing_ids 从 ChatRequest 透传

Mock 策略：
  无 — Planner 不调用 retrieve / LLM，纯 Python 规则。

怎么跑：
  pytest tests/test_planner.py -q
  pytest -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from app.agents.planner import run_planner
from app.schemas import ChatRequest, QueryIntent


def test_planner_qa_default() -> None:
    """常规研究问题 → QA + 需要检索。"""
    request = ChatRequest(
        query="What are the main risk factors?",
        ticker="AAPL",
    )
    plan, latency_ms = run_planner(request)

    assert plan.intent == QueryIntent.QA
    assert plan.need_retrieval is True
    assert plan.ticker == "AAPL"
    assert latency_ms >= 0.0
    assert "QA" in plan.rationale


def test_planner_refuse_investment_advice() -> None:
    """投资建议 → REFUSE，不检索。"""
    request = ChatRequest(query="Should I buy AAPL stock?")
    plan, _ = run_planner(request)

    assert plan.intent == QueryIntent.REFUSE
    assert plan.need_retrieval is False
    assert "refuse" in plan.rationale.lower()


def test_planner_refuse_buy_keyword() -> None:
    """单独 buy 整词也应 REFUSE。"""
    request = ChatRequest(query="Is now a good time to buy AAPL?")
    plan, _ = run_planner(request)

    assert plan.intent == QueryIntent.REFUSE
    assert plan.need_retrieval is False


def test_planner_summarize_intent() -> None:
    request = ChatRequest(query="Summarize the risk factors section", ticker="AAPL")
    plan, _ = run_planner(request)

    assert plan.intent == QueryIntent.SUMMARIZE
    assert plan.need_retrieval is True


def test_planner_diff_intent() -> None:
    request = ChatRequest(query="Compare 2024 vs 2025 risk factors", ticker="AAPL")
    plan, _ = run_planner(request)

    assert plan.intent == QueryIntent.DIFF
    assert plan.need_retrieval is True


def test_planner_passes_filing_ids() -> None:
    """filing_ids 应原样进 Plan。"""
    filing_ids = ["0000320193-25-000079"]
    request = ChatRequest(
        query="What is revenue?",
        ticker="AAPL",
        filing_ids=filing_ids,
    )
    plan, _ = run_planner(request)

    assert plan.filing_ids == filing_ids
    assert plan.intent == QueryIntent.QA