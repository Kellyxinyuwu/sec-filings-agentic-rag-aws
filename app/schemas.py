"""
API 与 agent 共用的数据结构（Pydantic）。

数据流:
  POST /retrieve: RetrieveRequest → tools.retrieve() → RetrieveResponse
  POST /chat:     ChatRequest → Plan → EvidenceChunk → ChatResponse

----------------------------------------------------------------------
QueryIntent — Planner 判断用户想干什么
  qa         问答，如「主要风险有哪些？」
  diff       对比两期 filing（Phase 3+）
  summarize  摘要某段/某文件
  refuse     拒答：投资建议、非公开数据等
----------------------------------------------------------------------
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    """
    用户意图枚举（Planner 输出 intent 时用）。

    - QA: 常规问答
    - DIFF: 两期 filing 对比
    - SUMMARIZE: 章节/文档摘要
    - REFUSE: 不应回答
    """

    QA = "qa"
    DIFF = "diff"
    SUMMARIZE = "summarize"
    REFUSE = "refuse"


class Plan(BaseModel):
    """
    Planner agent 的执行计划。

    - intent: 任务类型（QueryIntent）
    - need_retrieval: 是否查向量库；False 可不检索直接拒答
    - ticker: 股票代码，如 AAPL
    - filing_ids: 限定 filing；空则按 ticker 自动选
    - sections: 限定章节，如 Item 1A
    - rationale: 简短理由，便于日志/调试
    """

    intent: QueryIntent = QueryIntent.QA
    need_retrieval: bool = True
    ticker: str | None = None
    filing_ids: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    rationale: str = ""


class EvidenceChunk(BaseModel):
    """
    RAG 检索出的一块证据（原文片段 + 出处）。

    - chunk_id: 唯一 ID，引用用
    - filing_id / ticker / section: 来自哪份 filing、哪一节
    - excerpt: 原文摘录
    - score: 相关度（可选）
    - metadata: 扩展字段（页码、日期等）
    """

    chunk_id: str
    filing_id: str
    ticker: str
    section: str
    excerpt: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePack(BaseModel):
    """
    一次检索的完整结果（Researcher → Writer）。

    - query: 检索 query（可与用户原问略有不同）
    - chunks: 多块 EvidenceChunk
    """

    query: str
    chunks: list[EvidenceChunk] = Field(default_factory=list)


class Citation(BaseModel):
    """
    答案里展示的引用（对应某块 EvidenceChunk，字段更少便于展示）。

    - chunk_id: 指向证据块
    - filing_id, section, excerpt: 出处说明
    """

    chunk_id: str
    filing_id: str
    section: str
    excerpt: str


class AgentStep(BaseModel):
    """
    编排流水线中的一步（写入 ChatResponse，便于观测）。

    - step: 如 planner, researcher, writer, verifier
    - latency_ms: 耗时（毫秒）
    - detail: 可选说明，如 mock pass、retry once
    """

    step: str
    latency_ms: float | None = None
    detail: str | None = None


class ChatRequest(BaseModel):
    """
    POST /chat 请求体。

    - query: 用户问题（必填）
    - ticker: 可选，缩小到公司
    - filing_ids: 可选，指定 filing
    - session_id: 可选，多轮对话（Phase 3+）
    """

    query: str
    ticker: str | None = None
    filing_ids: list[str] = Field(default_factory=list)
    session_id: str | None = None


class ChatResponse(BaseModel):
    """
    POST /chat 响应。

    - answer: 最终答案
    - citations: 引用列表
    - evidence: 用到的证据块
    - trace_id: 本次请求 ID，查日志用
    - agent_steps: 各步耗时
    - plan: 可选，返回 Planner 计划便于调试
    """

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceChunk] = Field(default_factory=list)
    trace_id: str
    agent_steps: list[AgentStep] = Field(default_factory=list)
    plan: Plan | None = None



class RetrieveRequest(BaseModel):
    """
    POST /retrieve 请求体（Phase 1 纯检索，不生成答案）。

    - query:  检索问题，如 "What are the main risk factors?"
    - ticker: 可选，限定公司（Phase 1 建议传 AAPL）
    - top_k:  返回几条证据（默认 5）
    """

    query: str
    ticker: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class RetrieveResponse(BaseModel):
    """
    POST /retrieve 响应体。

    - query:  回显请求里的 query
    - chunks: 检索到的 EvidenceChunk 列表（来自 tools.retrieve）
  """

    query: str
    chunks: list[EvidenceChunk] = Field(default_factory=list)