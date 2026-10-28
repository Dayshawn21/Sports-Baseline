import type { AskEvent, AskStop } from '~/types/ask'
import { toolLabel } from '~/utils/askStatus'

export interface AskToolLine {
  name: string
  label: string
  state: 'running' | 'ok' | 'failed'
}

export interface AskTurn {
  id: number
  question: string
  tools: AskToolLine[]
  text: string
  stop: AskStop | null
  error: string | null
  status: 'running' | 'done' | 'error' | 'stopped'
}

export type AskAction =
  | { type: 'start'; question: string }
  | { type: 'event'; event: AskEvent }
  | { type: 'fail'; message: string }
  | { type: 'stop' }

function applyEvent(turn: AskTurn, event: AskEvent): AskTurn {
  switch (event.type) {
    case 'tool_start':
      return { ...turn, tools: [...turn.tools, { name: event.name, label: toolLabel(event.name, event.sport), state: 'running' }] }
    case 'tool_end': {
      const at = turn.tools.findLastIndex(tool => tool.name === event.name && tool.state === 'running')
      if (at === -1) return turn
      const tools = turn.tools.map((tool, i) => (i === at ? { ...tool, state: event.ok ? ('ok' as const) : ('failed' as const) } : tool))
      return { ...turn, tools }
    }
    case 'text':
      return { ...turn, text: turn.text + event.delta }
    case 'done':
      // The final text replaces the deltas: it drops pre-tool "let me check"
      // text and carries the fixed refusal sentence.
      return { ...turn, text: event.text, stop: event.stop, status: 'done' }
    case 'error':
      return { ...turn, error: event.message, status: 'error' }
  }
}

function updateLast(turns: AskTurn[], update: (turn: AskTurn) => AskTurn): AskTurn[] {
  const last = turns.at(-1)
  if (!last || last.status !== 'running') return turns
  return [...turns.slice(0, -1), update(last)]
}

/** A gray note under a finished answer, or null when it needs none. */
export function turnNote(turn: AskTurn): string | null {
  if (turn.status === 'stopped') return 'Stopped.'
  if (turn.status !== 'done') return null
  if (turn.stop === 'truncated') return 'This answer hit its length limit and may be cut short.'
  if (turn.stop === 'iteration_limit') return 'Lineform stopped looking things up, so this answer may be incomplete.'
  return null
}

/**
 * One short line for the screen reader's live region: tool steps and the end
 * of an answer, never the streaming text itself.
 */
export function turnAnnouncement(turn: AskTurn | undefined): string {
  if (!turn) return ''
  switch (turn.status) {
    case 'running': {
      const tool = turn.tools.findLast(line => line.state === 'running')
      return tool ? `${tool.label}...` : 'Asking Lineform...'
    }
    case 'done':
      return 'Answer ready.'
    case 'error':
      return turn.error ?? 'Something went wrong.'
    case 'stopped':
      return 'Stopped.'
  }
}

/** Every question asked in this drawer, oldest first; only the last can still be running. */
export function askReducer(turns: AskTurn[], action: AskAction): AskTurn[] {
  switch (action.type) {
    case 'start': {
      const stopped = updateLast(turns, turn => ({ ...turn, status: 'stopped' }))
      const id = (turns.at(-1)?.id ?? 0) + 1
      return [...stopped, { id, question: action.question, tools: [], text: '', stop: null, error: null, status: 'running' }]
    }
    case 'event':
      return updateLast(turns, turn => applyEvent(turn, action.event))
    case 'fail':
      return updateLast(turns, turn => ({ ...turn, error: action.message, status: 'error' }))
    case 'stop':
      return updateLast(turns, turn => ({ ...turn, status: 'stopped' }))
  }
}
