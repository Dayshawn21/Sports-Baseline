import type { AskEvent, AskSport, AskStop } from '~/types/ask'

const SPORTS: readonly string[] = ['nba', 'nfl', 'tennis'] satisfies AskSport[]
const STOPS: readonly string[] = ['answered', 'truncated', 'refused', 'iteration_limit', 'error'] satisfies AskStop[]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function toEvent(name: string, data: unknown): AskEvent | null {
  if (!isRecord(data)) return null
  switch (name) {
    case 'tool_start':
      if (typeof data.name !== 'string') return null
      return {
        type: 'tool_start',
        name: data.name,
        sport: typeof data.sport === 'string' && SPORTS.includes(data.sport) ? (data.sport as AskSport) : null,
      }
    case 'tool_end':
      return typeof data.name === 'string' && typeof data.ok === 'boolean'
        ? { type: 'tool_end', name: data.name, ok: data.ok }
        : null
    case 'text':
      return typeof data.delta === 'string' ? { type: 'text', delta: data.delta } : null
    case 'done':
      return typeof data.stop === 'string' && STOPS.includes(data.stop) && typeof data.text === 'string'
        ? { type: 'done', stop: data.stop as AskStop, text: data.text }
        : null
    case 'error':
      return typeof data.message === 'string' ? { type: 'error', message: data.message } : null
    default:
      return null
  }
}

function parseFrame(frame: string): AskEvent | null {
  let name = 'message'
  const data: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue
    if (line.startsWith('event:')) name = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''))
  }
  if (data.length === 0) return null
  try {
    return toEvent(name, JSON.parse(data.join('\n')))
  } catch {
    return null
  }
}

/**
 * Complete frames in `buffer` as events, and the unfinished tail to prepend to
 * the next read. Pings, unknown events and malformed frames are dropped.
 */
export function parseSseChunks(buffer: string): { events: AskEvent[]; rest: string } {
  // Only CRLF is normalized: a lone CR may be the first half of a pair split across reads.
  const frames = buffer.replace(/\r\n/g, '\n').split('\n\n')
  const rest = frames.pop() ?? ''
  const events = frames.map(parseFrame).filter((event): event is AskEvent => event !== null)
  return { events, rest }
}
