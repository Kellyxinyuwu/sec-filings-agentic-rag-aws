"""
Bedrock Mantle chat client — OpenAI-compatible Chat Completions API.

Endpoint: settings.mantle_base_url (e.g. https://bedrock-mantle.us-east-1.api.aws/v1)
Auth:     settings.mantle_api_key (Bedrock API key from Mantle console)

Phase 2 only — api.py / llm.py call this module, not OpenAI SDK directly.
"""

from __future__ import annotations

import structlog
from openai import OpenAI

from app.config import settings

log = structlog.get_logger()


def _require_mantle_config() -> None:
    if not settings.mantle_api_key:
        raise ValueError(
            "MANTLE_API_KEY is empty — create a key in Bedrock Mantle Console "
            "(Account scope → API keys) and add it to .env"
        )
    if not settings.mantle_model_id:
        raise ValueError(
            "MANTLE_MODEL_ID is empty — e.g. qwen.qwen3-coder-next for Qwen3 Coder Next"
        )


def _client() -> OpenAI:
    _require_mantle_config()
    return OpenAI(
        base_url=settings.mantle_base_url,
        api_key=settings.mantle_api_key,
        timeout=settings.mantle_timeout_seconds,
    )


def mantle_chat(
    *,
    system: str,
    user: str,
    max_tokens: int | None = None,
) -> str:
    """
    Single-turn chat via Mantle Chat Completions API.

    Args:
        system:     system prompt (RAG rules, citation format — Step 4)
        user:       user message (query + evidence text)
        max_tokens: cap output length; defaults to settings.mantle_max_tokens

    Returns:
        Assistant message text (stripped). Empty string if model returns no content.
    """
    model = settings.mantle_model_id
    limit = max_tokens if max_tokens is not None else settings.mantle_max_tokens

    log.info("mantle_chat_request", model=model, max_tokens=limit)

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
        "mantle_chat_done",
        model=model,
        output_chars=len(text),
        finish_reason=response.choices[0].finish_reason,
    )
    return text