"""
Tests for POST /chat — Phase 3 orchestrator path.

----------------------------------------------------------------------
测什么？
  - /chat 调 app.api.run_chat（不再直接 retrieve + llm_chat）
  - 响应契约：answer、citations、evidence、agent_steps、plan

Mock 策略：
  patch app.api.run_chat — 返回预制 ChatResponse，CI 不连 DB/Mantle。

怎么跑：
  pytest tests/test_chat_rag.py -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    AgentStep,
    ChatResponse,
    Citation,
    EvidenceChunk,
    Plan,
    QueryIntent,
)

client = TestClient(app)

SAMPLE_CHUNK = EvidenceChunk(
    chunk_id="AAPL-test-chat-001",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Risk factors include supply chain disruption.",
    score=0.88,
)

MOCK_ANSWER = (
    "Based on the evidence, main risks include supply chain disruption "
    "[AAPL-test-chat-001]."
)

MOCK_PLAN = Plan(
    intent=QueryIntent.QA,
    need_retrieval=True,
    ticker="AAPL",
    rationale="Planner: QA — retrieve SEC evidence then grounded answer",
)

MOCK_RESPONSE = ChatResponse(
    answer=MOCK_ANSWER,
    citations=[
        Citation(
            chunk_id=SAMPLE_CHUNK.chunk_id,
            filing_id=SAMPLE_CHUNK.filing_id,
            section=SAMPLE_CHUNK.section,
            excerpt=SAMPLE_CHUNK.excerpt,
        )
    ],
    evidence=[SAMPLE_CHUNK],
    trace_id="test-trace-chat-rag",
    agent_steps=[
        AgentStep(step="planner", latency_ms=0.5, detail="qa"),
        AgentStep(step="researcher", latency_ms=2.0, detail="1 chunks"),
        AgentStep(step="writer", latency_ms=10.0, detail="mantle"),
        AgentStep(step="verifier", latency_ms=0.2, detail="citations ok"),
    ],
    plan=MOCK_PLAN,
)


@pytest.fixture
def mock_run_chat(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock orchestrator entry — keeps /chat tests offline."""
    from app import api

    mock = MagicMock(return_value=MOCK_RESPONSE)
    monkeypatch.setattr(api, "run_chat", mock)
    return mock


def test_chat_returns_grounded_answer(mock_run_chat: MagicMock) -> None:
    response = client.post(
        "/chat",
        json={"query": "What are the main risk factors?", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    body = response.json()

    assert MOCK_ANSWER in body["answer"]
    assert "[Mock response]" not in body["answer"]
    assert body["trace_id"]

    mock_run_chat.assert_called_once()
    call_request = mock_run_chat.call_args.args[0]
    assert call_request.query == "What are the main risk factors?"
    assert call_request.ticker == "AAPL"
    assert mock_run_chat.call_args.kwargs["trace_id"]


def test_chat_citations_and_evidence(mock_run_chat: MagicMock) -> None:
    response = client.post(
        "/chat",
        json={"query": "Risk factors?", "ticker": "AAPL"},
    )
    body = response.json()

    assert len(body["citations"]) == 1
    assert body["citations"][0]["chunk_id"] == SAMPLE_CHUNK.chunk_id
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["ticker"] == "AAPL"


def test_chat_agent_steps(mock_run_chat: MagicMock) -> None:
    response = client.post(
        "/chat",
        json={"query": "Risk?", "ticker": "AAPL"},
    )
    steps = {s["step"]: s for s in response.json()["agent_steps"]}

    assert steps["planner"]["detail"] == "qa"
    assert steps["researcher"]["detail"] == "1 chunks"
    assert steps["verifier"]["detail"] == "citations ok"
    assert "mock pass" not in steps["verifier"]["detail"]


def test_chat_plan_from_planner(mock_run_chat: MagicMock) -> None:
    plan = response.json()["plan"] if (response := client.post(
        "/chat",
        json={"query": "Risk?", "ticker": "AAPL"},
    )).status_code == 200 else {}
    assert plan.get("intent") == "qa"
    assert plan.get("need_retrieval") is True
    assert "Planner" in plan.get("rationale", "")