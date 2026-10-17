export type QueryIntent = 'qa' | 'diff' | 'summarize' | 'refuse'

export interface Plan {
  intent: QueryIntent
  need_retrieval: boolean
  ticker: string | null
  filing_ids: string[]
  sections: string[]
  rationale: string
}

export interface EvidenceChunk {
  chunk_id: string
  filing_id: string
  ticker: string
  section: string
  excerpt: string
  score: number | null
  metadata: Record<string, unknown>
}

export interface Citation {
  chunk_id: string
  filing_id: string
  section: string
  excerpt: string
}

export interface AgentStep {
  step: string
  latency_ms: number | null
  detail: string | null
}

export interface ChatRequest {
  query: string
  ticker?: string | null
  filing_ids?: string[]
  session_id?: string | null
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  evidence: EvidenceChunk[]
  trace_id: string
  agent_steps: AgentStep[]
  plan: Plan | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  ticker?: string
  response?: ChatResponse
  error?: string
}
