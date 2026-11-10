export function marketCountLabel(count: number): string {
  return `${count} ${count === 1 ? 'market' : 'markets'}`
}

export const PAYOUT_TIER_NOTE = 'Goblin and demon are PrizePicks payout tiers: a goblin line sits below the standard line and pays less, a demon line sits above it and pays more. Both take the over only. The tier is not a signal.'

/** The goblin and demon explainer when any of a lines table's type labels is one, else null. */
export function payoutTierNote(types: string[]): string | null {
  return types.some(type => /^(goblin|demon)$/i.test(type.trim())) ? PAYOUT_TIER_NOTE : null
}

export type PlayerTagTone = 'default' | 'caution' | 'out'

/** An injury designation's tag tone: none is plain, Out reads strongest, anything else is a caution. Gray in every case. */
export function injuryTone(status: string | null): PlayerTagTone {
  if (status === null || status.trim() === '') return 'default'
  return status.trim().toLowerCase() === 'out' ? 'out' : 'caution'
}

/** The newest of a set of timestamps, for a "lines as of" footer; null when none parses. */
export function latestTime(values: Array<string | null>): string | null {
  let latest: string | null = null
  for (const value of values) {
    if (value === null || !Number.isFinite(Date.parse(value))) continue
    if (latest === null || Date.parse(value) > Date.parse(latest)) latest = value
  }
  return latest
}
