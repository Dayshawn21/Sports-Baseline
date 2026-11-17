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

/** Router state a prop board row sets, so the player page can send Back to the board instead of the slate. */
export const FROM_BOARD = { from: 'board' } as const

export function arrivedFromBoard(state: unknown): boolean {
  return typeof state === 'object' && state !== null && (state as { from?: unknown }).from === 'board'
}

/** The query string with `updates` applied; a null value removes the key, so other params (market, form) survive a change to one. */
export function playerSearch(params: URLSearchParams, updates: Record<string, string | null>): string {
  const next = new URLSearchParams(params)
  for (const [key, value] of Object.entries(updates)) {
    if (value === null) next.delete(key)
    else next.set(key, value)
  }
  const text = next.toString()
  return text ? `?${text}` : '?'
}

/** One DOM id per prop section, in order; a market that repeats gets a numeric suffix so ids never collide. */
export function propSectionIds(markets: string[]): string[] {
  const seen = new Map<string, number>()
  return markets.map(market => {
    const count = (seen.get(market) ?? 0) + 1
    seen.set(market, count)
    return count === 1 ? `prop-${market}` : `prop-${market}-${count}`
  })
}

/** The tabs are the response's markets in the order the API sent them, each once. */
export function playerTabs<M extends string>(markets: readonly { market: M }[]): M[] {
  return markets.map(item => item.market).filter((market, index, all) => all.indexOf(market) === index)
}

/** The `?market=` tab when it is one of the player's markets, else the first. */
export function selectedMarket<M extends string>(params: URLSearchParams, markets: readonly M[]): M | null {
  const asked = params.get('market')
  return markets.find(market => market === asked) ?? markets[0] ?? null
}
