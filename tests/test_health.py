from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_mock() -> None:
    response = client.post(
        "/chat",
        json={"query": "What are risk factors?", "ticker": "AAPL"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert body["citations"]
    assert body["trace_id"]
