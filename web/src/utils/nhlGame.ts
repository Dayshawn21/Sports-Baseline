import type { NhlBook, NhlSlateGame } from '~/types/nhl'
import { fmtAmerican } from '~/utils/odds'
import { isResultPending } from '~/utils/slateOrder'
import { dayClockCt } from '~/utils/slatePeriod'

const FULL_TIME = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})

export function validNhlGameId(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value > 0
}

export const validNhlPlayerId = validNhlGameId

export function parseNhlGameId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null
  const id = Number(value)
  return validNhlGameId(id) ? id : null
}

export function nhlTimeLabel(value: string | null, full = false): string {
  const time = value === null ? NaN : Date.parse(value)
  if (!Number.isFinite(time)) return '--'
  return full ? `${FULL_TIME.format(time)} CT` : dayClockCt(time)
}

export function nhlPuckDropLabel(value: string | null, full = false): string {
  const label = nhlTimeLabel(value, full)
  return label === '--' ? 'Time TBD' : label
}

/** `pending`: over by the clock, with no final stored yet. */
export type NhlGameState = 'upcoming' | 'started' | 'pending' | 'final' | 'off'

export function nhlGameState(game: NhlSlateGame, now: Date): { state: NhlGameState, label: string } {
  if (game.status === 'completed') {
    return { state: 'final', label: game.endPeriod === 'OT' || game.endPeriod === 'SO' ? `Final / ${game.endPeriod}` : 'Final' }
  }
  if (game.status === 'postponed') return { state: 'off', label: 'Postponed' }
  if (game.status === 'canceled') return { state: 'off', label: 'Canceled' }
  if (isResultPending(game.startUtc, now)) return { state: 'pending', label: 'Result pending' }
  const start = game.startUtc === null ? NaN : Date.parse(game.startUtc)
  return Number.isFinite(start) && start <= now.getTime()
    ? { state: 'started', label: 'Puck dropped' }
    : { state: 'upcoming', label: 'Scheduled' }
}

const NHL_BOOK_LABELS: Record<NhlBook, string> = { draftkings: 'DraftKings', fanduel: 'FanDuel', bet365: 'Bet365' }

export function nhlBookLabel(book: NhlBook): string {
  return NHL_BOOK_LABELS[book]
}

export function signedNhlLine(line: number): string {
  return `${line > 0 ? '+' : ''}${Object.is(line, -0) ? '0.0' : line.toFixed(1)}`
}

export interface NhlMarketCell {
  label: string
  value: string
  detail: string
  book: NhlBook | null
  fetchedAt: string | null
}

/** Home then away; source/timestamp stay attached to each independent market. */
export function nhlMarketCells(game: NhlSlateGame): NhlMarketCell[] {
  const { spread, total, moneyline } = game
  const missing = (label: string): NhlMarketCell => ({ label, value: '--', detail: 'Not stored', book: null, fetchedAt: null })
  return [
    spread === null ? missing('Puck line') : {
      label: 'Puck line', value: `${game.homeTeam} ${signedNhlLine(spread.homeLine)} (${fmtAmerican(spread.homeOdds)})`,
      detail: `${game.awayTeam} ${signedNhlLine(-spread.homeLine)} (${fmtAmerican(spread.awayOdds)})`,
      book: spread.book, fetchedAt: spread.fetchedAt,
    },
    total === null ? missing('Total') : {
      label: 'Total', value: total.line.toFixed(1),
      detail: `Over ${fmtAmerican(total.overOdds)} / Under ${fmtAmerican(total.underOdds)}`,
      book: total.book, fetchedAt: total.fetchedAt,
    },
    moneyline === null ? missing('Moneyline') : {
      label: 'Moneyline', value: `${game.homeTeam} ${fmtAmerican(moneyline.homeOdds)}`,
      detail: `${game.awayTeam} ${fmtAmerican(moneyline.awayOdds)}`,
      book: moneyline.book, fetchedAt: moneyline.fetchedAt,
    },
  ]
}

export function nhlMarketProbability(game: NhlSlateGame): NhlMarketCell {
  const { moneyline } = game
  const label = 'Market win probability'
  if (moneyline === null) return { label, value: '--', detail: 'No moneyline stored', book: null, fetchedAt: null }
  const home = moneyline.homeWinProbability * 100
  return {
    label, value: `${game.homeTeam} ${home.toFixed(1)}% / ${game.awayTeam} ${(100 - home).toFixed(1)}%`,
    detail: 'De-vigged book probability, includes OT/SO', book: moneyline.book, fetchedAt: moneyline.fetchedAt,
  }
}
