import type { AdoptedPick } from '~/types/tennis'
import { mainRung } from '~/utils/nflLineOnly'

/** Whether a row's line is an adopted pick (48e) or reference only. Only an adopted row may show green or red. */
export type RowSignal = { kind: 'reference' } | { kind: 'adopted', side: 'over' | 'under' }

export const REFERENCE: RowSignal = { kind: 'reference' }

export type Tone = 'neutral' | 'positive' | 'negative'

/** A tennis line is adopted only when 48e's check adopted it; rated alone stays reference. */
export function tennisRowSignal(line: { adoptedPick?: AdoptedPick | null }): RowSignal {
  return line.adoptedPick ? { kind: 'adopted', side: line.adoptedPick.side } : REFERENCE
}

/** The one place a board row's color is decided: gray unless adopted, then whether the direction agrees with the pick. */
export function agreementTone(signal: RowSignal, direction: 'over' | 'under' | 'push' | null): Tone {
  if (signal.kind === 'reference' || direction === null || direction === 'push') return 'neutral'
  return direction === signal.side ? 'positive' : 'negative'
}

const BAR_DIRECTION = { above: 'over', below: 'under', push: 'push' } as const

/** A recent-game bar's tone: it agrees with an adopted pick when it landed on the picked side of the line. */
export function barTone(signal: RowSignal, vsLine: 'above' | 'below' | 'push' | null): Tone {
  return agreementTone(signal, vsLine === null ? null : BAR_DIRECTION[vsLine])
}

export interface AltRung {
  line: number
  oddsType: string | null
  note?: string | null
}

export interface AltGroup<R extends AltRung> {
  main: R
  alts: R[]
  count: number
}

const ODDS_TYPE_ORDER: Record<string, number> = { standard: 0, goblin: 1, demon: 2 }

function oddsTypeRank(oddsType: string | null): number {
  return ODDS_TYPE_ORDER[oddsType ?? 'standard'] ?? 3
}

/** The rung the Line cell shows, plus every other rung for the alts chip; null when there are no rungs. */
export function groupAltLines<R extends AltRung>(rungs: readonly R[]): AltGroup<R> | null {
  if (!rungs.length) return null
  const main = mainRung({ rungs: [...rungs] })
  const alts = rungs
    .filter(rung => rung !== main)
    .sort((a, b) => a.line - b.line || oddsTypeRank(a.oddsType) - oddsTypeRank(b.oddsType))
  return { main, alts, count: alts.length }
}

function clampPct(value: number): number {
  return Math.min(100, Math.max(0, value))
}

export interface RingModel {
  /** P(over), 0 to 100. */
  pct: number
  /** The share the arc draws: P(over), or P(under) on an adopted under so the toned arc is always the picked side. */
  arcPct: number
  breakEvenPct: number | null
  tone: Tone
}

/** `pct` is 0-100; callers convert NBA and NHL 0-1 probabilities. Null draws no ring. */
export function probabilityRing(pct: number | null, signal: RowSignal, breakEvenPct: number | null = null): RingModel | null {
  if (pct === null || Number.isNaN(pct)) return null
  const over = clampPct(pct)
  const pickedUnder = signal.kind === 'adopted' && signal.side === 'under'
  return {
    pct: over,
    arcPct: pickedUnder ? 100 - over : over,
    breakEvenPct: breakEvenPct === null ? null : clampPct(breakEvenPct),
    tone: signal.kind === 'adopted' ? 'positive' : 'neutral',
  }
}

export interface StatCell {
  key: 'l5' | 'l10' | 'avg' | 'diff'
  label: string
  value: string
  tone: Tone
}

function signed(value: number): string {
  const rounded = Math.round(value * 10) / 10
  return `${rounded > 0 ? '+' : ''}${rounded.toFixed(1)}`
}

function majority(hits: number, games: number): 'over' | 'under' | 'push' {
  return hits * 2 > games ? 'over' : hits * 2 < games ? 'under' : 'push'
}

function hitCell(key: 'l5' | 'l10', values: readonly number[], line: number, signal: RowSignal): StatCell {
  const hits = values.filter(value => value > line).length
  return { key, label: `L${values.length}`, value: `${hits}/${values.length}`, tone: agreementTone(signal, majority(hits, values.length)) }
}

/**
 * Hit counts, average and diff from the games the row already carries, newest first. L10 appears only with
 * ten games served; the average and diff use the longest window shown. A push is never counted as a hit.
 */
export function statStrip(values: readonly number[], line: number | null, signal: RowSignal): StatCell[] {
  if (line === null || !values.length) return []
  const recent = values.slice(0, 5)
  const cells = [hitCell('l5', recent, line, signal)]
  const window = values.length >= 10 ? values.slice(0, 10) : recent
  if (window.length === 10) cells.push(hitCell('l10', window, line, signal))
  const average = window.reduce((total, value) => total + value, 0) / window.length
  const diff = average - line
  const direction = diff > 0 ? 'over' : diff < 0 ? 'under' : 'push'
  cells.push(
    { key: 'avg', label: 'Avg', value: (Math.round(average * 10) / 10).toFixed(1), tone: 'neutral' },
    { key: 'diff', label: 'Diff', value: signed(diff), tone: agreementTone(signal, direction) },
  )
  return cells
}
