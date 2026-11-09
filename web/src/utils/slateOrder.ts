/** Where a game stands for display: still in play first, settled last. Never an input to an edge or rank. */
export type SlatePhase = 'live' | 'upcoming' | 'off' | 'final'

const PHASE_ORDER: Record<SlatePhase, number> = { live: 0, upcoming: 1, off: 2, final: 3 }

/** The four sports' row states, as phases: NBA and NHL say "started" for a game in play, and a game whose result is pending has ended. */
export function slatePhase(state: 'upcoming' | 'live' | 'started' | 'pending' | 'final' | 'off'): SlatePhase {
  if (state === 'started') return 'live'
  return state === 'pending' ? 'final' : state
}

/** No NFL, NBA or NHL game runs this long, overtime included; past it, a game with no result has ended and only its score is missing. */
export const RESULT_PENDING_AFTER_MS = 5 * 60 * 60 * 1000

/** True for a game started over five hours ago; callers ask only of games not yet marked final or off. */
export function isResultPending(startUtc: string | null, now: Date): boolean {
  const start = startUtc === null ? Number.NaN : Date.parse(startUtc)
  return Number.isFinite(start) && now.getTime() - start > RESULT_PENDING_AFTER_MS
}

/** Live, then upcoming, then off, then final; a stable sort, so games keep their order within a phase. */
export function orderByPhase<T>(items: readonly T[], phaseOf: (item: T) => SlatePhase): T[] {
  return items
    .map((item, index) => ({ item, index, rank: PHASE_ORDER[phaseOf(item)] }))
    .sort((left, right) => left.rank - right.rank || left.index - right.index)
    .map(({ item }) => item)
}

/** A day slate split for display: games still to settle in phase order, and every final kept in its own order. */
export function splitFinals<T>(items: readonly T[], phaseOf: (item: T) => SlatePhase): { open: T[], finals: T[] } {
  return {
    open: orderByPhase(items.filter(item => phaseOf(item) !== 'final'), phaseOf),
    finals: items.filter(item => phaseOf(item) === 'final'),
  }
}

/** Start windows in order of their most urgent game, so a window with a live game leads; a stable sort otherwise. */
export function orderWindowsByPhase<W extends { games: readonly G[] }, G>(windows: readonly W[], phaseOf: (game: G) => SlatePhase): W[] {
  const rank = (window: W) => Math.min(...window.games.map(game => PHASE_ORDER[phaseOf(game)]))
  return windows
    .map((window, index) => ({ window, index, rank: rank(window) }))
    .sort((left, right) => left.rank - right.rank || left.index - right.index)
    .map(({ window }) => window)
}

/** The finals window opens by itself only when nothing else is left to show: an all-final slate, or a search. */
export function finalsStartOpen(openCount: number, searching: boolean): boolean {
  return openCount === 0 || searching
}

/** A day slate's one window of unsettled games; once some games are final it holds only what is left. */
export function openWindowTitle(finals: number): string {
  return finals > 0 ? 'Still to play' : 'All games'
}
