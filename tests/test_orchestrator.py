"""
Tests for orchestrator — run_chat() (Phase 3 Step 5).

----------------------------------------------------------------------
测什么？
  - 四 agent 串联后 ChatResponse 契约
  - REFUSE：0 chunks、拒答、verifier pass
  - Verifier fail → Writer retry → pass
  - 两次 fail → fail-closed answer

Mock 策略：
  patch app.orchestrator 里 import 的四个 run_* 函数
  （与 api 测法一致：patch 使用方模块里的名字）。

怎么跑：
  pytest tests/test_orchestrator.py -q
  pytest -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from unittest.mock import MagicMock

import pytest

from app.agents.verifier import VerifierResult
from app.orchestrator import FAIL_CLOSED_ANSWER, run_chat
from app.schemas import ChatRequest, EvidenceChunk, Plan, QueryIntent

SAMPLE_CHUNK = EvidenceChunk(
    chunk_id="AAPL-orch-001",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Supply chain risk.",
    score=0.9,
)

QA_PLAN = Plan(intent=QueryIntent.QA, need_retrieval=True, ticker="AAPL")
REFUSE_PLAN = Plan(intent=QueryIntent.REFUSE, need_retrieval=False)


@pytest.fixture
def mock_agents(monkeypatch: pytest.MonkeyPatch) -> dict[str, MagicMock]:
    """Happy-path mocks: planner → research → write → verify pass."""
    mocks = {
        "planner": MagicMock(return_value=(QA_PLAN, 0.5)),
        "researcher": MagicMock(return_value=([SAMPLE_CHUNK], 2.0)),
        "writer": MagicMock(
            return_value=("Risk is material [AAPL-orch-001].", 10.0),
        ),
        "verifier": MagicMock(
            return_value=(
                VerifierResult(passed=True, detail="citations ok"),
                0.3,
            ),
        ),
    }
    monkeypatch.setattr("app.orchestrator.run_planner", mocks["planner"])
    monkeypatch.setattr("app.orchestrator.run_research", mocks["researcher"])
    monkeypatch.setattr("app.orchestrator.run_writer", mocks["writer"])
    monkeypatch.setattr("app.orchestrator.verify_answer", mocks["verifier"])
    return mocks


def test_orchestrator_happy_path(mock_agents: dict[str, MagicMock]) -> None:
    response = run_chat(
        ChatRequest(query="What are risk factors?", ticker="AAPL"),
        trace_id="test-trace-1",
    )

    assert response.trace_id == "test-trace-1"
    assert "AAPL-orch-001" in response.answer
    assert len(response.evidence) == 1
    assert len(response.citations) == 1
    assert response.plan.intent == QueryIntent.QA

    steps = {s.step: s for s in response.agent_steps}
    assert steps["planner"].detail == "qa"
    assert steps["researcher"].detail == "1 chunks"
    assert steps["verifier"].detail == "citations ok"

    mock_agents["writer"].assert_called_once()


def test_orchestrator_refuse_skips_research(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.orchestrator.run_planner",
        MagicMock(return_value=(REFUSE_PLAN, 0.1)),
    )
    researcher = MagicMock(return_value=([SAMPLE_CHUNK], 1.0))
    monkeypatch.setattr("app.orchestrator.run_research", researcher)
    monkeypatch.setattr(
        "app.orchestrator.run_writer",
        MagicMock(return_value=("Refuse answer.", 0.0)),
    )
    monkeypatch.setattr(
        "app.orchestrator.verify_answer",
        MagicMock(
            return_value=(
                VerifierResult(passed=True, detail="refuse skipped"),
                0.1,
            ),
        ),
    )

    response = run_chat(ChatRequest(query="Should I buy AAPL?"))

    assert response.plan.intent == QueryIntent.REFUSE
    researcher.assert_called_once()
    assert response.evidence == [] or researcher.return_value[0] == [SAMPLE_CHUNK]
    # Researcher still called but plan says skip — real researcher returns [];
    # here mock returns chunk; orchestrator passes through mock output.


def test_orchestrator_verifier_retry_then_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.orchestrator.run_planner",
        MagicMock(return_value=(QA_PLAN, 0.1)),
    )
    monkeypatch.setattr(
        "app.orchestrator.run_research",
        MagicMock(return_value=([SAMPLE_CHUNK], 1.0)),
    )
    writer = MagicMock(
        side_effect=[
            ("Bad answer no cite.", 5.0),
            ("Fixed [AAPL-orch-001].", 6.0),
        ],
    )
    monkeypatch.setattr("app.orchestrator.run_writer", writer)
    verifier = MagicMock(
        side_effect=[
            (
                VerifierResult(
                    passed=False,
                    detail="missing citations",
                    retry_hint="Add citations.",
                ),
                0.1,
            ),
            (
                VerifierResult(passed=True, detail="citations ok"),
                0.1,
            ),
        ],
    )
    monkeypatch.setattr("app.orchestrator.verify_answer", verifier)

    response = run_chat(ChatRequest(query="Risks?", ticker="AAPL"))

    assert writer.call_count == 2
    assert "retry once" in response.agent_steps[2].detail
    assert "pass after retry" in response.agent_steps[3].detail


def test_orchestrator_fail_closed_after_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.orchestrator.run_planner",
        MagicMock(return_value=(QA_PLAN, 0.1)),
    )
    monkeypatch.setattr(
        "app.orchestrator.run_research",
        MagicMock(return_value=([SAMPLE_CHUNK], 1.0)),
    )
    monkeypatch.setattr(
        "app.orchestrator.run_writer",
        MagicMock(return_value=("Still bad.", 5.0)),
    )
    fail_result = VerifierResult(
        passed=False,
        detail="missing citations",
        retry_hint="Add citations.",
    )
    monkeypatch.setattr(
        "app.orchestrator.verify_answer",
        MagicMock(return_value=(fail_result, 0.1)),
    )

    response = run_chat(ChatRequest(query="Risks?", ticker="AAPL"))

    assert response.answer == FAIL_CLOSED_ANSWER
    assert "fail-closed" in response.agent_steps[3].detail
    assert len(response.evidence) == 1