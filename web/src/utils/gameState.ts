import { isResultPending } from '~/utils/slateOrder'
import { CENTRAL_TZ } from '~/utils/format'

const FULL = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL_TZ, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
const CLOCK = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL_TZ, hour: 'numeric', minute: '2-digit' })
const DAY = new Intl.DateTimeFormat('en-US', { timeZone: CENTRAL_TZ, weekday: 'short', month: 'short', day: 'numeric' })

/**
 * `live`: started by the clock, not yet completed. Scores load after the game, so nothing live is claimed beyond that.
 * `pending`: over by the clock, still waiting on the ingest that stores the final.
 */
export type GamePhase = 'upcoming' | 'live' | 'pending' | 'final' | 'off'

export interface GameState { phase: GamePhase, label: string }

/**
 * One rule for every game page, slate card and board; `status` is the API's stored status, which stays "scheduled"
 * until the final loads. `startedLabel` lets a sport name the live phase in its own words ("Tipped off").
 */
export function gameState(status: string, startUtc: string | null, now: Date, startedLabel = 'In progress'): GameState {
  const stored = status.toLowerCase()
  if (stored === 'completed') return { phase: 'final', label: 'Final' }
  if (stored === 'postponed') return { phase: 'off', label: 'Postponed' }
  if (stored === 'canceled' || stored === 'cancelled') return { phase: 'off', label: 'Canceled' }
  if (isResultPending(startUtc, now)) return { phase: 'pending', label: 'Result pending' }
  const start = parseStart(startUtc)
  return start !== null && start <= now.getTime() ? { phase: 'live', label: startedLabel } : { phase: 'upcoming', label: 'Scheduled' }
}

function parseStart(startUtc: string | null): number | null {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isFinite(time) ? time : null
}

/** `Sun, Nov 9, 12:00 PM CT`, for the meta line. */
export function gameStartLabel(startUtc: string | null): string {
  const start = parseStart(startUtc)
  return start === null ? 'Start time not set' : `${FULL.format(start)} CT`
}

/** The hero's split start: `12:00 PM CT` over `Sun, Nov 9`; null without a time. */
export function gameStartParts(startUtc: string | null): { clock: string, day: string } | null {
  const start = parseStart(startUtc)
  return start === null ? null : { clock: `${CLOCK.format(start)} CT`, day: DAY.format(start) }
}

/** NHL finals name an overtime or shootout ending: `Final/OT`. */
export function withEndPeriod(state: GameState, endPeriod: string | null): GameState {
  return state.phase === 'final' && (endPeriod === 'OT' || endPeriod === 'SO') ? { ...state, label: `Final/${endPeriod}` } : state
}
