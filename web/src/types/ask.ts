export type AskSport = 'nba' | 'nfl' | 'tennis'

export type AskStop = 'answered' | 'truncated' | 'refused' | 'iteration_limit' | 'error'

export interface AskStatus {
  enabled: boolean
}

/** One server-sent frame from `POST /ask`, in the order the API sends them. */
export type AskEvent =
  | { type: 'tool_start'; name: string; sport: AskSport | null }
  | { type: 'tool_end'; name: string; ok: boolean }
  | { type: 'text'; delta: string }
  | { type: 'done'; stop: AskStop; text: string }
  | { type: 'error'; message: string }

export type AnswerSegment =
  | { kind: 'text'; text: string }
  | { kind: 'link'; text: string; path: string }

export type AnswerBlock =
  | { kind: 'paragraph'; segments: AnswerSegment[] }
  | { kind: 'list'; items: AnswerSegment[][] }
