"""
Tests for POST /chat (Phase 2 RAG path).

CI: mock app.api.retrieve + app.api.llm_chat — no Postgres, no Mantle.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceChunk

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


@pytest.fixture
def mock_chat_pipeline(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    """Mock retrieve + LLM — keeps /chat tests offline."""
    from app import api

    mock_retrieve = MagicMock(return_value=[SAMPLE_CHUNK])
    mock_llm = MagicMock(return_value=MOCK_ANSWER)
    monkeypatch.setattr(api, "retrieve", mock_retrieve)
    monkeypatch.setattr(api, "llm_chat", mock_llm)
    return mock_retrieve, mock_llm


def test_chat_returns_grounded_answer(mock_chat_pipeline: tuple[MagicMock, MagicMock]) -> None:
    mock_retrieve, mock_llm = mock_chat_pipeline

    response = client.post(
        "/chat",
        json={"query": "What are the main risk factors?", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    body = response.json()

    assert MOCK_ANSWER in body["answer"]
    assert "[Mock response]" not in body["answer"]
    assert body["trace_id"]

    mock_retrieve.assert_called_once_with(
        "What are the main risk factors?",
        ticker="AAPL",
        top_k=5,
    )
    mock_llm.assert_called_once()
    _system, _user = mock_llm.call_args.kwargs["system"], mock_llm.call_args.kwargs["user"]
    assert "Question:" in _user
    assert SAMPLE_CHUNK.chunk_id in _user


def test_chat_citations_and_evidence(mock_chat_pipeline: tuple[MagicMock, MagicMock]) -> None:
    response = client.post(
        "/chat",
        json={"query": "Risk factors?", "ticker": "AAPL"},
    )
    body = response.json()

    assert len(body["citations"]) == 1
    assert body["citations"][0]["chunk_id"] == SAMPLE_CHUNK.chunk_id
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["ticker"] == "AAPL"


def test_chat_agent_steps(mock_chat_pipeline: tuple[MagicMock, MagicMock]) -> None:
    response = client.post(
        "/chat",
        json={"query": "Risk?", "ticker": "AAPL"},
    )
    steps = {s["step"]: s for s in response.json()["agent_steps"]}

    assert steps["researcher"]["detail"] == "1 chunks"
    assert steps["writer"]["detail"] == "mantle"
    assert steps["verifier"]["detail"] == "mock pass"


def test_chat_plan_rationale(mock_chat_pipeline: tuple[MagicMock, MagicMock]) -> None:
    plan = response.json()["plan"] if (response := client.post(
        "/chat",
        json={"query": "Risk?", "ticker": "AAPL"},
    )).status_code == 200 else {}
    assert plan.get("intent") == "qa"
    assert plan.get("need_retrieval") is True
    assert "Phase 2" in plan.get("rationale", "")