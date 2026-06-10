"""
Tests for POST /retrieve.

CI: monkeypatch app.api.retrieve — no Postgres, no SentenceTransformer load.
Local integration: curl against running API + ingested DB (Step 10).
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceChunk

client = TestClient(app)

SAMPLE_CHUNK = EvidenceChunk(
    chunk_id="chunk-test-1",
    filing_id="0000320193-25-000079",
    ticker="AAPL",
    section="Item 1A",
    excerpt="Risk factors include supply chain and competition.",
    score=0.85,
)


@pytest.fixture
def mock_retrieve(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace DB search with a fixed chunk — keeps CI offline."""
    from app import api

    mock = MagicMock(return_value=[SAMPLE_CHUNK])
    # api.py does `from app.tools import retrieve` — patch the name api uses.
    monkeypatch.setattr(api, "retrieve", mock)
    return mock


def test_health_phase_1() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "1"


def test_retrieve_returns_chunks(mock_retrieve: MagicMock) -> None:
    response = client.post(
        "/retrieve",
        json={
            "query": "What are the main risk factors?",
            "ticker": "AAPL",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["query"] == "What are the main risk factors?"
    assert len(body["chunks"]) == 1

    chunk = body["chunks"][0]
    assert chunk["chunk_id"] == SAMPLE_CHUNK.chunk_id
    assert chunk["ticker"] == "AAPL"
    assert chunk["section"] == "Item 1A"
    assert "Risk factors" in chunk["excerpt"]
    assert chunk["score"] == pytest.approx(0.85)

    mock_retrieve.assert_called_once_with(
        "What are the main risk factors?",
        ticker="AAPL",
        top_k=3,
    )


def test_retrieve_defaults_top_k(mock_retrieve: MagicMock) -> None:
    response = client.post(
        "/retrieve",
        json={"query": "revenue growth"},
    )
    assert response.status_code == 200
    mock_retrieve.assert_called_once_with(
        "revenue growth",
        ticker=None,
        top_k=5,
    )


def test_retrieve_rejects_invalid_top_k() -> None:
    response = client.post(
        "/retrieve",
        json={"query": "test", "top_k": 0},
    )
    assert response.status_code == 422

    response = client.post(
        "/retrieve",
        json={"query": "test", "top_k": 21},
    )
    assert response.status_code == 422


def test_retrieve_empty_chunks(mock_retrieve: MagicMock) -> None:
    mock_retrieve.return_value = []
    response = client.post(
        "/retrieve",
        json={"query": "nonexistent topic xyz", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    assert response.json()["chunks"] == []