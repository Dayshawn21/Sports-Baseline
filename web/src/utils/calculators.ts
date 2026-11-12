import { americanToProb } from '~/utils/odds'
import {
  americanToDecimal,
  breakEvenProbability,
  decimalToAmerican,
  expectedValue,
  impliedProbFromAmerican,
  KELLY_MAX_FRACTION,
  kellyFraction,
  overround,
  probToAmerican,
} from '~/utils/oddsMath'
import { parseAmerican, parseDecimal, parsePercent, parsePositive, type Parsed } from '~/utils/calculatorInputs'
import { entryEv, payoutTable, type EntryKind } from '~/utils/prizepicksEntry'

/** What each /tools card shows, derived from its raw field text so the components only render. */

export type OddsFormat = 'american' | 'decimal' | 'probability'

export interface ConvertedOdds { american: number, decimal: number, probability: number }

export interface NoVigResult {
  fairA: number
  fairB: number
  americanA: number
  americanB: number
  overround: number
}

export interface EvResult {
  ev: number
  /** EV in stake units; null when no stake was entered. */
  evAmount: number | null
  breakEven: number
}

export interface KellyResult {
  fraction: number
  /** Stake in bankroll units; null when no bankroll was entered. */
  stake: number | null
  /** The 25% ceiling, not the formula, set the fraction. */
  capped: boolean
}

export interface EntryRow {
  hits: number
  probability: number
  /** Payout multiple at this hit count; null when it pays nothing. */
  multiple: number | null
}

export interface EntryView {
  rows: EntryRow[]
  expectedMultiple: number
  ev: number
}

/** Any invalid field wins (named by its label), then any empty field keeps the card quiet. */
function pair(labelA: string, a: Parsed<number>, labelB: string, b: Parsed<number>): Parsed<[number, number]> {
  if (a.state === 'invalid') return { state: 'invalid', reason: `${labelA}: ${a.reason}` }
  if (b.state === 'invalid') return { state: 'invalid', reason: `${labelB}: ${b.reason}` }
  if (a.state === 'empty' || b.state === 'empty') return { state: 'empty' }
  return { state: 'ok', value: [a.value, b.value] }
}

function map<T, U>(parsed: Parsed<T>, fn: (value: T) => U): Parsed<U> {
  return parsed.state === 'ok' ? { state: 'ok', value: fn(parsed.value) } : parsed
}

export function convertOdds(format: OddsFormat, text: string): Parsed<ConvertedOdds> {
  if (format === 'american') {
    return map(parseAmerican(text), american => ({ american, decimal: americanToDecimal(american), probability: americanToProb(american) }))
  }
  if (format === 'decimal') {
    return map(parseDecimal(text), decimal => ({ american: decimalToAmerican(decimal), decimal, probability: breakEvenProbability(decimal) }))
  }
  return map(parsePercent(text), probability => ({ american: probToAmerican(probability), decimal: 1 / probability, probability }))
}

export function noVig(sideA: string, sideB: string): Parsed<NoVigResult> {
  return map(pair('Side A', parseAmerican(sideA), 'Side B', parseAmerican(sideB)), ([a, b]) => {
    const [fairA, fairB] = impliedProbFromAmerican(a, b)
    return {
      fairA,
      fairB,
      americanA: probToAmerican(fairA),
      americanB: probToAmerican(fairB),
      overround: overround(americanToProb(a), americanToProb(b)),
    }
  })
}

/** An optional amount: an invalid entry is reported, an empty one is simply absent. */
function optionalAmount(label: string, text: string): Parsed<number | null> {
  const parsed = parsePositive(text)
  if (parsed.state === 'invalid') return { state: 'invalid', reason: `${label}: ${parsed.reason}` }
  return { state: 'ok', value: parsed.state === 'ok' ? parsed.value : null }
}

export function betEv(probability: string, odds: string, stake: string): Parsed<EvResult> {
  const amount = optionalAmount('Stake', stake)
  if (amount.state !== 'ok') return amount
  return map(pair('Win probability', parsePercent(probability), 'Odds', parseAmerican(odds)), ([p, american]) => {
    const ev = expectedValue(p, american)
    return {
      ev,
      evAmount: amount.value === null ? null : ev * amount.value,
      breakEven: breakEvenProbability(americanToDecimal(american)),
    }
  })
}

export function kellyStake(probability: string, odds: string, multiplier: number, bankroll: string): Parsed<KellyResult> {
  const amount = optionalAmount('Bankroll', bankroll)
  if (amount.state !== 'ok') return amount
  return map(pair('Win probability', parsePercent(probability), 'Odds', parseAmerican(odds)), ([p, american]) => {
    const fraction = kellyFraction(p, american, KELLY_MAX_FRACTION, multiplier)
    return {
      fraction,
      stake: amount.value === null ? null : fraction * amount.value,
      capped: kellyFraction(p, american, Infinity, multiplier) > KELLY_MAX_FRACTION,
    }
  })
}

/** Per-leg percents to the hit-count rows the entry card lists, most hits first. */
export function entryView(kind: EntryKind, legs: string[]): Parsed<EntryView> {
  const probs: number[] = []
  let empty = false
  for (const [index, text] of legs.entries()) {
    const parsed = parsePercent(text)
    if (parsed.state === 'invalid') return { state: 'invalid', reason: `Leg ${index + 1}: ${parsed.reason}` }
    if (parsed.state === 'empty') empty = true
    else probs.push(parsed.value)
  }
  if (empty) return { state: 'empty' }
  const outcome = entryEv(probs, kind)
  const payouts = payoutTable(kind, probs.length)
  if (!outcome.ok) return { state: 'invalid', reason: outcome.reason }
  if (!payouts.ok) return { state: 'invalid', reason: payouts.reason }
  const rows = outcome.result.distribution
    .map((probability, hits) => ({ hits, probability, multiple: payouts.table[hits] ?? null }))
    .reverse()
  return { state: 'ok', value: { rows, expectedMultiple: outcome.result.expectedMultiple, ev: outcome.result.ev } }
}

/** A signed percent such as `+5.0%`; a value that rounds to zero carries no sign. */
export function fmtSignedPct(value: number, decimals = 1): string {
  const rounded = Number((value * 100).toFixed(decimals))
  const sign = rounded > 0 ? '+' : rounded < 0 ? '-' : ''
  return `${sign}${Math.abs(rounded).toFixed(decimals)}%`
}

/** Decimal odds to three places, trimmed to no fewer than two (`1.909`, `2.00`, `3.50`). */
export function fmtDecimalOdds(value: number): string {
  return value.toFixed(3).replace(/0$/, '')
}

/** A signed amount in stake units, such as `+5.00` or `-2.30`. */
export function fmtSignedAmount(value: number): string {
  const rounded = Number(value.toFixed(2))
  const sign = rounded > 0 ? '+' : rounded < 0 ? '-' : ''
  return `${sign}${Math.abs(rounded).toFixed(2)}`
}
