"""
Tests for Writer agent — run_writer() (Phase 3 Step 3).

----------------------------------------------------------------------
测什么？
  - QA + evidence → 调 llm_chat，prompt 里含 chunk_id
  - REFUSE plan → 固定拒答，不调 LLM
  - verifier_feedback → 追加进 user message（retry 路径）

Mock 策略：
  patch app.agents.writer.llm_chat（Writer 模块里的 import 名）。

怎么跑：
  pytest tests/test_writer.py -q
  pytest -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from unittest.mock import MagicMock

import pytest

from app.agents.writer import REFUSE_ANSWER, run_writer
from app.schemas import EvidenceChunk, Plan, QueryIntent

SAMPLE_CHUNK = EvidenceChunk(
    chunk_id="AAPL-writer-001",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Supply chain disruption is a risk.",
    score=0.9,
)

MOCK_LLM_ANSWER = (
    "Main risks include supply chain disruption [AAPL-writer-001]."
)


@pytest.fixture
def mock_llm_chat(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock(return_value=MOCK_LLM_ANSWER)
    monkeypatch.setattr("app.agents.writer.llm_chat", mock)
    return mock


def test_writer_qa_calls_llm(mock_llm_chat: MagicMock) -> None:
    """正常 QA：build_rag_prompt → llm_chat，user 里含 evidence。"""
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True, ticker="AAPL")
    answer, latency_ms = run_writer(
        "What are risk factors?",
        plan,
        [SAMPLE_CHUNK],
    )

    assert answer == MOCK_LLM_ANSWER
    assert latency_ms >= 0.0
    mock_llm_chat.assert_called_once()
    _kwargs = mock_llm_chat.call_args.kwargs
    assert "Question:" in _kwargs["user"]
    assert SAMPLE_CHUNK.chunk_id in _kwargs["user"]
    assert _kwargs["system"]


def test_writer_refuse_skips_llm(mock_llm_chat: MagicMock) -> None:
    """REFUSE：固定文案，不调用 LLM。"""
    plan = Plan(intent=QueryIntent.REFUSE, need_retrieval=False)
    answer, _ = run_writer("Should I buy AAPL?", plan, [])

    assert answer == REFUSE_ANSWER
    mock_llm_chat.assert_not_called()


def test_writer_appends_verifier_feedback(mock_llm_chat: MagicMock) -> None:
    """Retry 路径：verifier_feedback 应追加到 user prompt。"""
    plan = Plan(intent=QueryIntent.QA, need_retrieval=True)
    feedback = "Missing citation for revenue claim."
    run_writer("Revenue?", plan, [SAMPLE_CHUNK], verifier_feedback=feedback)

    user_msg = mock_llm_chat.call_args.kwargs["user"]
    assert feedback in user_msg
    assert "Verifier feedback" in user_msg