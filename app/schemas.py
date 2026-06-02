from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    QA = "qa"
    DIFF = "diff"
    SUMMARIZE = "summarize"
    REFUSE = "refuse"


class Plan(BaseModel):
    """Planner output — drives Researcher and Writer."""

    intent: QueryIntent = QueryIntent.QA
    need_retrieval: bool = True
    ticker: str | None = None
    filing_ids: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    rationale: str = ""


class EvidenceChunk(BaseModel):
    chunk_id: str
    filing_id: str
    ticker: str
    section: str
    excerpt: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    query: str
    chunks: list[EvidenceChunk] = Field(default_factory=list)


class Citation(BaseModel):
    chunk_id: str
    filing_id: str
    section: str
    excerpt: str


class AgentStep(BaseModel):
    step: str
    latency_ms: float | None = None
    detail: str | None = None


class ChatRequest(BaseModel):
    query: str
    ticker: str | None = None
    filing_ids: list[str] = Field(default_factory=list)
    session_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    trace_id: str
    agent_steps: list[AgentStep] = Field(default_factory=list)
    plan: Plan | None = None
