import client from './client'
import type { AskEvent, AskStatus } from '~/types/ask'
import { resolveApiBaseUrl } from '~/utils/apiBase'
import { parseSseChunks } from '~/utils/askStream'

const API_BASE = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL)

export class AskHttpError extends Error {
  /** `detail` is the API's own, or null when the body was not its JSON (a proxy page, say). */
  constructor(
    readonly status: number,
    readonly detail: string | null,
    fallback: string,
    readonly retryAfter: number | null = null,
  ) {
    super(detail ?? fallback)
    this.name = 'AskHttpError'
  }
}

export async function fetchAskStatus(): Promise<AskStatus> {
  const { data } = await client.get<AskStatus>('/ask/status')
  return data
}

async function errorDetail(res: Response): Promise<string | null> {
  try {
    const body: unknown = await res.json()
    if (typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string') {
      return body.detail
    }
  } catch {
    // Not JSON: no detail to show.
  }
  return null
}

/** POST one question and call `onEvent` per frame. EventSource cannot POST, so this reads the body itself. */
export async function streamAsk(
  question: string,
  { signal, onEvent }: { signal: AbortSignal; onEvent: (event: AskEvent) => void },
): Promise<void> {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!res.ok) {
    const retryAfter = Number.parseInt(res.headers.get('Retry-After') ?? '', 10)
    throw new AskHttpError(
      res.status, await errorDetail(res), res.statusText || `HTTP ${res.status}`,
      Number.isNaN(retryAfter) ? null : retryAfter,
    )
  }
  if (!res.body) throw new AskHttpError(res.status, null, 'The answer stream was empty.')

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    const { events, rest } = parseSseChunks(buffer + value)
    buffer = rest
    events.forEach(onEvent)
  }
}
