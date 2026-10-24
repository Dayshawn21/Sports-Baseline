import type { NhlBook, NhlSlateGame } from '~/types/nhl'
import { fmtAmerican } from '~/utils/odds'

const SHORT_TIME = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', weekday: 'short', hour: 'numeric', minute: '2-digit',
})
const FULL_TIME = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})

export function validNhlGameId(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value > 0
}

export function parseNhlGameId(value: string | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null
  const id = Number(value)
  return validNhlGameId(id) ? id : null
}

export function nhlTimeLabel(value: string | null, full = false): string {
  const time = value === null ? NaN : Date.parse(value)
  return Number.isFinite(time) ? `${(full ? FULL_TIME : SHORT_TIME).format(time)} CT` : '--'
}

export function nhlPuckDropLabel(value: string | null, full = false): string {
  const label = nhlTimeLabel(value, full)
  return label === '--' ? 'Time TBD' : label
}

export type NhlGameState = 'upcoming' | 'started' | 'final' | 'off'

export function nhlGameState(game: NhlSlateGame, now: Date): { state: NhlGameState, label: string } {
  if (game.status === 'completed') {
    return { state: 'final', label: game.endPeriod === 'OT' || game.endPeriod === 'SO' ? `Final / ${game.endPeriod}` : 'Final' }
  }
  if (game.status === 'postponed') return { state: 'off', label: 'Postponed' }
  if (game.status === 'canceled') return { state: 'off', label: 'Canceled' }
  const start = game.startUtc === null ? NaN : Date.parse(game.startUtc)
  return Number.isFinite(start) && start <= now.getTime()
    ? { state: 'started', label: 'Puck dropped' }
    : { state: 'upcoming', label: 'Scheduled' }
}

export function nhlBookLabel(book: NhlBook): string {
  return book === 'draftkings' ? 'DraftKings' : 'Bet365'
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
