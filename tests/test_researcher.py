"""
Tests for Researcher agent — run_research() (Phase 3 Step 1).

----------------------------------------------------------------------
测什么？
  - app.agents.researcher.run_research(query, plan) 单元逻辑
  - 正常 QA：调 retrieve，返回 chunks + latency
  - 默认 ticker=AAPL
  - need_retrieval=False 时早停，不查库

和 test_retrieve.py / test_chat_rag.py 的区别？
  那些测 HTTP API；本文件直接调 Python 函数（更细、更快）。

Mock 策略：
  patch app.agents.researcher.retrieve（researcher 模块里的 import 名）。

怎么跑：
  pytest tests/test_researcher.py -q
  pytest -q   # 全量回归
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from unittest.mock import MagicMock

import pytest

from app.agents.researcher import run_research
from app.schemas import EvidenceChunk, Plan, QueryIntent

SAMPLE_CHUNK = EvidenceChunk(
    chunk_id="AAPL-researcher-001",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Supply chain risk.",
    score=0.91,
)


@pytest.fixture
def mock_retrieve(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """把真 retrieve 换成假函数，返回固定 SAMPLE_CHUNK。"""
    mock = MagicMock(return_value=[SAMPLE_CHUNK])
    monkeypatch.setattr("app.agents.researcher.retrieve", mock)
    return mock


def test_run_research_returns_chunks(mock_retrieve: MagicMock) -> None:
    """正常 QA：应返回 chunk，并带上 latency。"""
    plan = Plan(ticker="AAPL", intent=QueryIntent.QA, need_retrieval=True)
    chunks, latency_ms = run_research("What are risk factors?", plan)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == SAMPLE_CHUNK.chunk_id
    assert latency_ms >= 0.0

    mock_retrieve.assert_called_once_with(
        "What are risk factors?",
        ticker="AAPL",
        top_k=5,
    )


def test_run_research_default_ticker(mock_retrieve: MagicMock) -> None:
    """Plan 没写 ticker 时，Researcher 应默认 AAPL（与 Phase 2 api.py 一致）。"""
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    run_research("Revenue?", plan)

    mock_retrieve.assert_called_once_with("Revenue?", ticker="AAPL", top_k=5)


def test_run_research_skipped_when_no_retrieval(mock_retrieve: MagicMock) -> None:
    """REFUSE / need_retrieval=False：早停，retrieve 一次都不能被调用。"""
    plan = Plan(intent=QueryIntent.REFUSE, need_retrieval=False)
    chunks, latency_ms = run_research("Buy AAPL?", plan)

    assert chunks == []
    assert latency_ms == 0.0
    mock_retrieve.assert_not_called()
