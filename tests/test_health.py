"""
Tests for basic API health and minimal /chat contract (Phase 0+).

----------------------------------------------------------------------
测什么？
  - GET /health 是否 200、status=ok
  - POST /chat 是否返回 answer、citations、trace_id

Mock 策略（Phase 3）：
  patch app.api.run_chat — /chat 走 orchestrator，不再 mock retrieve/llm。

怎么跑：
  pytest tests/test_health.py -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ChatResponse, Citation, EvidenceChunk

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "3"


@pytest.fixture
def mock_chat_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock orchestrator — minimal ChatResponse for smoke test."""
    from app import api

    chunk = EvidenceChunk(
        chunk_id="health-test-chunk",
        filing_id="0000320193-25-000079",
        ticker="AAPL",
        section="Item 1A",
        excerpt="Sample risk excerpt.",
        score=0.5,
    )
    monkeypatch.setattr(
        api,
        "run_chat",
        MagicMock(
            return_value=ChatResponse(
                answer="Test answer [health-test-chunk].",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        filing_id=chunk.filing_id,
                        section=chunk.section,
                        excerpt=chunk.excerpt,
                    )
                ],
                evidence=[chunk],
                trace_id="health-trace",
            )
        ),
    )


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