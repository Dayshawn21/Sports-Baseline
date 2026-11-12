/** Port of `app/core/prizepicks_entry.py`, held to the same fixture cases. */

export type EntryKind = 'power' | 'flex'

export const MIN_LEGS = 2
export const MAX_LEGS = 6

/** Standard payout multiples, checked 2026-11-11; keep in step with the Python table. */
export const POWER_PAYOUTS: Record<number, number> = { 2: 3, 3: 6, 4: 10, 5: 20, 6: 37.5 }
export const FLEX_PAYOUTS: Record<number, Record<number, number>> = {
  3: { 3: 3, 2: 1 },
  4: { 4: 6, 3: 1.5 },
  5: { 5: 10, 4: 2, 3: 0.4 },
  6: { 6: 25, 5: 2, 4: 0.4 },
}

export interface EntryResult {
  /** P(exactly k legs hit), indexed by k. */
  distribution: number[]
  expectedMultiple: number
  ev: number
}

export type EntryOutcome = { ok: true, result: EntryResult } | { ok: false, reason: string }

export type PayoutOutcome = { ok: true, table: Record<number, number> } | { ok: false, reason: string }

export function hitCountDistribution(probs: number[]): number[] {
  let dist = [1]
  for (const p of probs) {
    const next = new Array<number>(dist.length + 1).fill(0)
    dist.forEach((mass, hits) => {
      next[hits] += mass * (1 - p)
      next[hits + 1] += mass * p
    })
    dist = next
  }
  return dist
}

/** Payout multiple by hit count, or why PrizePicks does not offer the entry. */
export function payoutTable(kind: string, legs: number): PayoutOutcome {
  if (legs < MIN_LEGS || legs > MAX_LEGS) return { ok: false, reason: `An entry has ${MIN_LEGS} to ${MAX_LEGS} legs.` }
  if (kind === 'power') return { ok: true, table: { [legs]: POWER_PAYOUTS[legs] } }
  if (kind === 'flex') {
    const table = FLEX_PAYOUTS[legs]
    return table ? { ok: true, table } : { ok: false, reason: 'Flex needs at least 3 legs.' }
  }
  return { ok: false, reason: `Unknown entry type "${kind}".` }
}

export function entryEv(probs: number[], kind: string): EntryOutcome {
  const payouts = payoutTable(kind, probs.length)
  if (!payouts.ok) return payouts
  if (probs.some(p => !(p >= 0 && p <= 1))) return { ok: false, reason: 'Leg probabilities must be between 0% and 100%.' }
  const distribution = hitCountDistribution(probs)
  const expectedMultiple = Object.entries(payouts.table)
    .reduce((sum, [hits, multiple]) => sum + distribution[Number(hits)] * multiple, 0)
  return { ok: true, result: { distribution, expectedMultiple, ev: expectedMultiple - 1 } }
}
