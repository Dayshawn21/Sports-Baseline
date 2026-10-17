import type { MatchOddsMarket, MatchOddsRow } from '~/types/tennis'
import { devigP1 } from '~/utils/odds'

export interface MovementPoint {
  at: string
  /** De-vigged p1 probability for moneyline; the line for total games. */
  value: number
}

export interface BookSeries {
  book: string
  points: MovementPoint[]
}

export type MoveDirection = 'toward' | 'away' | 'flat'

export interface MoveSummary {
  open: number
  latest: number
  /** How far the price closed the gap to the model, in percentage points; negative moved away. */
  towardModelPts: number | null
  direction: MoveDirection | null
}

function pointValue(row: MatchOddsRow, market: MatchOddsMarket): number | null {
  return market === 'moneyline' ? devigP1(row.p1Odds, row.p2Odds) : row.line
}

export function buildMovementSeries(rows: MatchOddsRow[], market: MatchOddsMarket): BookSeries[] {
  const byBook = new Map<string, MovementPoint[]>()
  for (const row of rows) {
    const value = pointValue(row, market)
    if (value == null) continue
    const points = byBook.get(row.book) ?? []
    points.push({ at: row.fetchedAt, value })
    byBook.set(row.book, points)
  }
  return [...byBook].map(([book, points]) => ({
    book,
    points: [...points].sort((a, b) => Date.parse(a.at) - Date.parse(b.at)),
  }))
}

// Same order the API breaks same-run ties in (_BOOK_PRIORITY_SQL); Bet365 was once stored as betonline.
const BOOK_PRIORITY = ['draftkings', 'bet365', 'betonline.ag', 'betonline', 'betfair exchange']

function bookRank(book: string): number {
  const rank = BOOK_PRIORITY.indexOf(book.toLowerCase())
  return rank === -1 ? BOOK_PRIORITY.length : rank
}

const BOOK_LABELS: Record<string, string> = {
  draftkings: 'DraftKings',
  bet365: 'Bet365',
  'betonline.ag': 'Bet365',
  betonline: 'Bet365',
  'betfair exchange': 'Betfair',
}

export function bookLabel(book: string): string {
  return BOOK_LABELS[book.toLowerCase()] ?? book
}

/** The series the chart footer summarizes: the book the slate would read first. */
export function preferredSeries(series: BookSeries[]): BookSeries | null {
  return [...series].sort((a, b) => bookRank(a.book) - bookRank(b.book))[0] ?? null
}

/** Each book's newest usable row (both prices for moneyline, a line for totals), in slate book order. */
export function latestPerBook(rows: MatchOddsRow[], market: MatchOddsMarket): MatchOddsRow[] {
  const latest = new Map<string, MatchOddsRow>()
  for (const row of rows) {
    if (pointValue(row, market) == null) continue
    const seen = latest.get(row.book)
    if (!seen || Date.parse(row.fetchedAt) >= Date.parse(seen.fetchedAt)) latest.set(row.book, row)
  }
  return [...latest.values()].sort((a, b) => bookRank(a.book) - bookRank(b.book))
}

const FLAT_PTS = 0.05

export function summarizeMove(series: BookSeries, modelValue: number | null): MoveSummary | null {
  const first = series.points[0]
  const last = series.points[series.points.length - 1]
  if (!first || !last) return null
  if (modelValue == null) {
    return { open: first.value, latest: last.value, towardModelPts: null, direction: null }
  }
  const towardModelPts = (Math.abs(first.value - modelValue) - Math.abs(last.value - modelValue)) * 100
  const direction: MoveDirection = Math.abs(towardModelPts) < FLAT_PTS
    ? 'flat'
    : towardModelPts > 0 ? 'toward' : 'away'
  return { open: first.value, latest: last.value, towardModelPts, direction }
}

/** Moneyline series are p1 probabilities; the page reads them from the hero side. */
export function seriesForSide(series: BookSeries[], side: 'p1' | 'p2'): BookSeries[] {
  if (side === 'p1') return series
  return series.map((s) => ({ ...s, points: s.points.map((pt) => ({ ...pt, value: 1 - pt.value })) }))
}

export interface ChartScale {
  tMin: number
  tMax: number
  vMin: number
  vMax: number
}

/** Bounds covering every point and any reference values, padded, and never narrower than minSpan. */
export function chartScale(series: BookSeries[], references: number[], minSpan: number): ChartScale | null {
  const points = series.flatMap((s) => s.points)
  if (points.length === 0) return null
  const times = points.map((pt) => Date.parse(pt.at))
  const values = [...points.map((pt) => pt.value), ...references]
  let vMin = Math.min(...values)
  let vMax = Math.max(...values)
  const pad = Math.max((vMax - vMin) * 0.15, (minSpan - (vMax - vMin)) / 2, 0)
  vMin -= pad
  vMax += pad
  return { tMin: Math.min(...times), tMax: Math.max(...times), vMin, vMax }
}

/** x and y as 0-1 fractions of the plot; a single moment sits in the middle. */
export function project(scale: ChartScale, at: string, value: number): { x: number; y: number } {
  const span = scale.tMax - scale.tMin
  const x = span === 0 ? 0.5 : (Date.parse(at) - scale.tMin) / span
  const y = (scale.vMax - value) / (scale.vMax - scale.vMin)
  return { x, y }
}
