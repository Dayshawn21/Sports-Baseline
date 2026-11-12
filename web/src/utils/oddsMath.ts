import { americanToProb } from '~/utils/odds'

/** Line-for-line ports of `app/core/odds.py`, `kelly.py` and `prop_ev.py`, held to the same fixture. */

export const DEFAULT_KELLY_MULTIPLIER = 0.25
export const KELLY_MAX_FRACTION = 0.25

/** Python's `round`: ties go to the even integer, where `Math.round` sends 112.5 to 113. */
export function roundHalfEven(x: number): number {
  return Math.abs(x % 1) === 0.5 ? 2 * Math.round(x / 2) : Math.round(x)
}

export function americanToDecimal(odds: number): number {
  return odds >= 0 ? 1 + odds / 100 : 1 + 100 / Math.abs(odds)
}

export function decimalToAmerican(dec: number): number {
  if (dec >= 2) return roundHalfEven((dec - 1) * 100)
  if (dec <= 1) return -10000
  return roundHalfEven(-100 / (dec - 1))
}

export function probToAmerican(p: number): number {
  const clamped = Math.max(1e-6, Math.min(0.999999, p))
  if (clamped >= 0.5) return roundHalfEven((-100 * clamped) / (1 - clamped))
  return roundHalfEven((100 * (1 - clamped)) / clamped)
}

export function breakEvenProbability(decimalOdds: number): number {
  return decimalOdds <= 0 ? 1 : 1 / decimalOdds
}

export function devigTwoWay(p1Raw: number, p2Raw: number): [number, number] {
  const total = p1Raw + p2Raw
  if (total <= 0) return [0.5, 0.5]
  return [p1Raw / total, p2Raw / total]
}

export function impliedProbFromAmerican(p1Odds: number, p2Odds: number): [number, number] {
  return devigTwoWay(americanToProb(p1Odds), americanToProb(p2Odds))
}

export function overround(p1Raw: number, p2Raw: number): number {
  return p1Raw + p2Raw - 1
}

/** Profit per unit staked when the bet wins. */
function netPayout(oddsAmerican: number): number {
  return oddsAmerican >= 0 ? oddsAmerican / 100 : 100 / Math.abs(oddsAmerican)
}

export function expectedValue(prob: number, oddsAmerican: number): number {
  return prob * netPayout(oddsAmerican) - (1 - prob)
}

export function kellyFraction(
  prob: number,
  oddsAmerican: number,
  maxFraction = KELLY_MAX_FRACTION,
  multiplier = DEFAULT_KELLY_MULTIPLIER,
): number {
  const b = netPayout(oddsAmerican)
  const k = (b * prob - (1 - prob)) / b
  return Math.max(0, Math.min(k * multiplier, maxFraction))
}
