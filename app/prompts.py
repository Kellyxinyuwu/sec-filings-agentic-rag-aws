"""
RAG prompt templates — format evidence + user query for llm.chat().

Flow (Step 5):
  retrieve() → list[EvidenceChunk]
            → build_rag_prompt(query, chunks) → (system, user)
            → llm.chat(system=system, user=user)

Grounding rules live in the system prompt; evidence text goes in the user message.
"""

from __future__ import annotations

from app.schemas import EvidenceChunk

# Per-chunk excerpt cap — controls INPUT tokens / cost (see docs/TOKEN_AND_COST_CONTROL.md).
# SEC raw HTML excerpts can be long; 1000 chars per chunk is enough for Phase 2 demo.
DEFAULT_MAX_EXCERPT_CHARS = 1000

RAG_SYSTEM_PROMPT = """You are a research assistant for SEC public filings (10-K / 10-Q).

Rules:
1. Answer ONLY using the evidence blocks provided in the user message. Do not use outside knowledge.
2. If the evidence does not support an answer, say clearly:
   "I cannot answer from the provided filings."
3. Cite sources using the exact chunk_id in square brackets, e.g. [AAPL-0000320193-25-000079-00217].
4. Do NOT give investment advice, price targets, or buy/sell recommendations.
5. Be concise and factual. Prefer bullet points for lists (e.g. risk factors).
6. The excerpts may contain HTML or formatting artifacts from EDGAR — focus on the substance.
"""


def _truncate(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def format_evidence_block(chunk: EvidenceChunk, *, max_excerpt_chars: int) -> str:
    """One evidence block for the user message."""
    excerpt = _truncate(chunk.excerpt, max_excerpt_chars)
    score_part = f" | relevance={chunk.score:.3f}" if chunk.score is not None else ""
    return (
        f"[chunk_id: {chunk.chunk_id}]\n"
        f"ticker: {chunk.ticker} | filing: {chunk.filing_id} | section: {chunk.section}"
        f"{score_part}\n"
        f"excerpt:\n{excerpt}"
    )


def build_rag_prompt(
    query: str,
    chunks: list[EvidenceChunk],
    *,
    max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
) -> tuple[str, str]:
    """
    Build (system, user) messages for llm.chat().

    Args:
        query:  User question (from ChatRequest.query)
        chunks: Evidence from tools.retrieve() — may be empty

    Returns:
        (system_prompt, user_message) ready for llm.chat(system=..., user=...)
    """
    query = query.strip()

    if not chunks:
        user = (
            f"Question: {query}\n\n"
            "Evidence: (none — no chunks retrieved from the database.)\n\n"
            "Reply that you cannot answer from the provided filings."
        )
        return RAG_SYSTEM_PROMPT, user

    blocks = [
        format_evidence_block(c, max_excerpt_chars=max_excerpt_chars)
        for c in chunks
    ]
    evidence_text = "\n\n---\n\n".join(blocks)

    user = (
        f"Question: {query}\n\n"
        f"Evidence ({len(chunks)} chunks):\n\n"
        f"{evidence_text}\n\n"
        "Answer the question using only the evidence above. Cite chunk_id for each key claim."
    )

    return RAG_SYSTEM_PROMPT, user