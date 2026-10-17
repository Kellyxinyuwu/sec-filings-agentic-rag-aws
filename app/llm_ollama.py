"""
Ollama chat client — OpenAI-compatible local inference (demo / offline).

Endpoint: settings.ollama_base_url (default http://127.0.0.1:11434/v1)
Auth:     dummy key (Ollama ignores it; OpenAI SDK requires a non-empty string)

Used when LLM_PROVIDER=ollama — no AWS account required.
"""

from __future__ import annotations

import structlog
from openai import OpenAI

from app.config import settings

log = structlog.get_logger()


def _require_ollama_config() -> None:
    if not settings.ollama_model_id:
        raise ValueError(
            "OLLAMA_MODEL_ID is empty — e.g. llama3.2 after `ollama pull llama3.2`"
        )
    if not settings.ollama_base_url:
        raise ValueError("OLLAMA_BASE_URL is empty — expected http://127.0.0.1:11434/v1")


def _client() -> OpenAI:
    _require_ollama_config()
    return OpenAI(
        base_url=settings.ollama_base_url,
        api_key="ollama",  # required by SDK; Ollama does not validate it
        timeout=settings.ollama_timeout_seconds,
    )


def ollama_chat(
    *,
    system: str,
    user: str,
    max_tokens: int | None = None,
) -> str:
    """
    Single-turn chat via local Ollama Chat Completions API.

    Returns:
        Assistant message text (stripped). Empty string if model returns no content.
    """
    model = settings.ollama_model_id
    limit = max_tokens if max_tokens is not None else settings.ollama_max_tokens

    log.info("ollama_chat_request", model=model, max_tokens=limit)

    response = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=limit,
    )

    choice = response.choices[0].message
    text = (choice.content or "").strip()

    log.info(
        "ollama_chat_done",
        model=model,
        output_chars=len(text),
        finish_reason=response.choices[0].finish_reason,
    )
    return text
