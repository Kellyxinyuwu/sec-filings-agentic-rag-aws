"""Unit tests for Ollama LLM provider wiring (mocked — no running Ollama)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app import llm as llm_mod
from app import llm_ollama


def test_chat_routes_to_ollama(monkeypatch):
    called: dict[str, object] = {}

    def fake_ollama_chat(*, system: str, user: str, max_tokens: int | None = None) -> str:
        called["system"] = system
        called["user"] = user
        called["max_tokens"] = max_tokens
        return "grounded answer [chunk-1]"

    monkeypatch.setattr(llm_mod.settings, "llm_provider", "ollama")
    monkeypatch.setattr(llm_ollama, "ollama_chat", fake_ollama_chat)
    # llm.chat imports ollama_chat inside the branch — patch the module attribute after import path
    monkeypatch.setattr("app.llm_ollama.ollama_chat", fake_ollama_chat)

    out = llm_mod.chat(system="sys", user="usr", max_tokens=64)
    assert out == "grounded answer [chunk-1]"
    assert called["system"] == "sys"
    assert called["user"] == "usr"
    assert called["max_tokens"] == 64


def test_ollama_chat_uses_openai_compatible_client(monkeypatch):
    monkeypatch.setattr(llm_ollama.settings, "ollama_model_id", "llama3.2")
    monkeypatch.setattr(llm_ollama.settings, "ollama_base_url", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(llm_ollama.settings, "ollama_max_tokens", 128)
    monkeypatch.setattr(llm_ollama.settings, "ollama_timeout_seconds", 30.0)

    mock_create = MagicMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="  hello from ollama  "),
                    finish_reason="stop",
                )
            ]
        )
    )
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    monkeypatch.setattr(llm_ollama, "_client", lambda: mock_client)

    text = llm_ollama.ollama_chat(system="s", user="u")
    assert text == "hello from ollama"
    kwargs = mock_create.call_args.kwargs
    assert kwargs["model"] == "llama3.2"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["max_tokens"] == 128
