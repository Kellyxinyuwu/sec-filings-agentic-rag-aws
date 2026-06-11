from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceChunk

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.fixture
def mock_chat_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 2: /chat needs mock retrieve + llm or pytest hits DB + Mantle."""
    from app import api

    chunk = EvidenceChunk(
        chunk_id="health-test-chunk",
        filing_id="0000320193-25-000079",
        ticker="AAPL",
        section="Item 1A",
        excerpt="Sample risk excerpt.",
        score=0.5,
    )
    monkeypatch.setattr(api, "retrieve", MagicMock(return_value=[chunk]))
    monkeypatch.setattr(api, "llm_chat", MagicMock(return_value="Test answer [health-test-chunk]."))


def test_chat_mock(mock_chat_pipeline: None) -> None:
    response = client.post(
        "/chat",
        json={"query": "What are risk factors?", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert body["citations"]
    assert body["trace_id"]
