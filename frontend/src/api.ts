import type { ChatRequest, ChatResponse } from './types'

/** Empty = Vite proxy `/api` → FastAPI :8001. Set VITE_API_BASE for a remote ALB. */
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

function chatUrl(): string {
  return API_BASE ? `${API_BASE}/chat` : '/api/chat'
}

export async function postChat(body: ChatRequest, signal?: AbortSignal): Promise<ChatResponse> {
  const res = await fetch(chatUrl(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = (await res.json()) as { detail?: unknown }
      if (data.detail != null) {
        detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
      }
    } catch {
      /* keep statusText */
    }
    throw new Error(`API ${res.status}: ${detail}`)
  }

  return (await res.json()) as ChatResponse
}
