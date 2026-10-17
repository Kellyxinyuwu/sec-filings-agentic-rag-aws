import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { postChat } from './api'
import type { ChatMessage, Citation } from './types'
import './App.css'

const SUGGESTIONS = [
  'What are the main risk factors?',
  'Summarize the business overview.',
  'What does the company say about competition?',
]

function uid(): string {
  return crypto.randomUUID()
}

/** Highlight [chunk_id] markers as clickable citation links. */
function AnswerText({
  text,
  onCite,
}: {
  text: string
  onCite: (chunkId: string) => void
}) {
  const parts = text.split(/(\[[^\]]+\])/g)
  return (
    <div className="answer-body">
      {parts.map((part, i) => {
        const m = part.match(/^\[([^\]]+)\]$/)
        if (m) {
          return (
            <button
              key={i}
              type="button"
              className="cite"
              onClick={() => onCite(m[1])}
              title={`Jump to ${m[1]}`}
            >
              [{m[1]}]
            </button>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </div>
  )
}

function SourcesPanel({
  citations,
  activeId,
  steps,
  onSelect,
}: {
  citations: Citation[]
  activeId: string | null
  steps: { step: string; latency_ms: number | null }[]
  onSelect: (id: string) => void
}) {
  const activeRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [activeId])

  return (
    <aside className="sources-panel" aria-label="Citations and evidence">
      <div className="sources-header">
        <h2>Sources</h2>
        <p>Cited filing excerpts from this answer</p>
      </div>

      <div className="sources-list">
        {citations.length === 0 ? (
          <p className="sources-empty">
            Ask a question to see chunk-level citations from the 10-K.
          </p>
        ) : (
          citations.map((c) => {
            const active = c.chunk_id === activeId
            return (
              <article
                key={c.chunk_id}
                className={`source-item${active ? ' active' : ''}`}
                ref={active ? activeRef : undefined}
                onClick={() => onSelect(c.chunk_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelect(c.chunk_id)
                  }
                }}
              >
                <header>
                  <span className="chunk-id">{c.chunk_id}</span>
                  <span className="section">{c.section || 'section n/a'}</span>
                  <span className="filing" title={c.filing_id}>
                    {c.filing_id}
                  </span>
                </header>
                <p className="excerpt">{c.excerpt}</p>
              </article>
            )
          })
        )}
      </div>

      {steps.length > 0 && (
        <div className="steps-bar" aria-label="Agent pipeline latency">
          {steps.map((s) => (
            <span key={s.step} className="step-pill">
              {s.step}
              {s.latency_ms != null ? ` · ${Math.round(s.latency_ms)}ms` : ''}
            </span>
          ))}
        </div>
      )}
    </aside>
  )
}

export default function App() {
  const [ticker, setTicker] = useState('AAPL')
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [activeCite, setActiveCite] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant' && m.response)
  const citations = lastAssistant?.response?.citations ?? []
  const steps = lastAssistant?.response?.agent_steps ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const tick = ticker.trim().toUpperCase() || 'AAPL'
    const userMsg: ChatMessage = {
      id: uid(),
      role: 'user',
      content: trimmed,
      ticker: tick,
    }

    setMessages((prev) => [...prev, userMsg])
    setQuery('')
    setLoading(true)
    setActiveCite(null)

    abortRef.current?.abort()
    const ac = new AbortController()
    abortRef.current = ac

    try {
      const data = await postChat(
        { query: trimmed, ticker: tick, filing_ids: [] },
        ac.signal,
      )
      const assistant: ChatMessage = {
        id: uid(),
        role: 'assistant',
        content: data.answer,
        response: data,
      }
      setMessages((prev) => [...prev, assistant])
      if (data.citations[0]) setActiveCite(data.citations[0].chunk_id)
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      const assistant: ChatMessage = {
        id: uid(),
        role: 'assistant',
        content: '',
        error: err instanceof Error ? err.message : 'Request failed',
      }
      setMessages((prev) => [...prev, assistant])
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(query)
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send(query)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="brand">
          Filing<span>Desk</span>
        </h1>
        <p className="tagline">Source-grounded Q&amp;A over SEC 10-K filings</p>
      </header>

      <div className="workspace">
        <section className="chat-column" aria-label="Chat">
          <div className="messages">
            {messages.length === 0 && !loading && (
              <div className="empty">
                <h2>Ask the filing</h2>
                <p>
                  Answers cite retrieved 10-K chunks. Investment advice is refused by
                  design.
                </p>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} type="button" onClick={() => void send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => {
              if (m.role === 'user') {
                return (
                  <div key={m.id} className="bubble user">
                    {m.content}
                  </div>
                )
              }
              if (m.error) {
                return (
                  <div key={m.id} className="bubble assistant error">
                    {m.error}
                  </div>
                )
              }
              const plan = m.response?.plan
              return (
                <div key={m.id} className="bubble assistant">
                  <AnswerText text={m.content} onCite={setActiveCite} />
                  {m.response && (
                    <div className="bubble-meta">
                      {plan && (
                        <span className="meta-chip">
                          <strong>intent</strong> {plan.intent}
                        </span>
                      )}
                      <span className="meta-chip">
                        <strong>trace</strong> {m.response.trace_id.slice(0, 8)}…
                      </span>
                      <span className="meta-chip">
                        <strong>cites</strong> {m.response.citations.length}
                      </span>
                    </div>
                  )}
                </div>
              )
            })}

            {loading && (
              <div className="bubble assistant">
                <div className="typing">
                  <span className="typing-dots" aria-hidden>
                    <span />
                    <span />
                    <span />
                  </span>
                  Retrieving &amp; writing (planner → researcher → writer → verifier)…
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={onSubmit}>
            <input
              className="ticker"
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              aria-label="Ticker"
              maxLength={8}
              disabled={loading}
            />
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask about risk factors, business, competition…"
              rows={1}
              disabled={loading}
              aria-label="Question"
            />
            <button className="send" type="submit" disabled={loading || !query.trim()}>
              Ask
            </button>
          </form>
        </section>

        <SourcesPanel
          citations={citations}
          activeId={activeCite}
          steps={steps}
          onSelect={setActiveCite}
        />
      </div>
    </div>
  )
}
