"""
Tests for POST /retrieve (Phase 1+).

----------------------------------------------------------------------
测什么？
  - GET /health 的 phase 字段（Phase 4 完成后期望 "4"）
  - POST /retrieve：JSON 形状、ticker/top_k 传参、空结果、非法 top_k

不测什么？
  不测真向量搜索质量 — 那靠 ingest + curl E2E。

Mock 策略：
  monkeypatch app.api.retrieve（api.py 里 from app.tools import retrieve）。
  返回固定的 SAMPLE_CHUNK，CI 无需 Postgres / SentenceTransformer。

怎么跑：
  pytest tests/test_retrieve.py -q
  详见 docs/PYTEST.md
----------------------------------------------------------------------
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import EvidenceChunk

client = TestClient(app)

# 模块级假数据：所有需要「有 chunk」的用例共用
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
    """替换向量检索为固定 chunk — 保持 CI offline。"""
    from app import api

    mock = MagicMock(return_value=[SAMPLE_CHUNK])
    # api.py: from app.tools import retrieve — patch api 模块里的名字
    monkeypatch.setattr(api, "retrieve", mock)
    return mock


def test_health_phase() -> None:
    """健康检查 + phase 版本号（Phase 4 AWS 数据面）。"""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == "4"
    assert body["vector_backend"] in ("local", "opensearch")


def test_retrieve_returns_chunks(mock_retrieve: MagicMock) -> None:
    """正常检索：响应含 query、chunks 字段，且 chunk 内容与 mock 一致。"""
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
    """未传 top_k 时，API 默认 top_k=5；ticker 可为 None。"""
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
    """Pydantic 校验：top_k 必须在 1–20，否则 422 Unprocessable Entity。"""
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
    """检索无结果时仍 200，chunks 为空列表（不是 404）。"""
    mock_retrieve.return_value = []
    response = client.post(
        "/retrieve",
        json={"query": "nonexistent topic xyz", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    assert response.json()["chunks"] == []
