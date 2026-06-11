"""
LLM provider abstraction — single entry point for all text generation.

Why this file exists:
  - api.py / agents / orchestrator call chat() only
  - Switch Mantle → classic Bedrock → Ollama by changing LLM_PROVIDER in .env
  - Never import OpenAI SDK or mantle_chat directly outside llm_* modules

See: docs/BEDROCK_MANTLE_VS_RUNTIME.md
"""

from __future__ import annotations

import structlog

from app.config import settings

log = structlog.get_logger()


def chat(
    *,
    system: str,
    user: str,
    max_tokens: int | None = None,
) -> str:
    """
    Generate assistant text from system + user messages.

    Args:
        system:     Instructions (RAG rules, citation format — from prompts.py)
        user:       User turn (query + evidence — from prompts.py)
        max_tokens: Cap completion length; provider-specific default if None

    Returns:
        Model response text.
    """
    provider = settings.llm_provider.strip().lower()
    log.info("llm_chat", provider=provider)

    if provider == "mantle":
        from app.llm_mantle import mantle_chat

        return mantle_chat(system=system, user=user, max_tokens=max_tokens)

    if provider == "bedrock":
        raise NotImplementedError(
            "LLM_PROVIDER=bedrock not implemented yet — use mantle, or add app/llm_bedrock.py "
            "after classic bedrock-runtime is enabled."
        )

    if provider == "ollama":
        raise NotImplementedError(
            "LLM_PROVIDER=ollama not implemented yet — optional fallback; see docs."
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER={settings.llm_provider!r} — expected mantle, bedrock, or ollama"
    )