import { queryOptions, skipToken } from '@tanstack/react-query'
import { fetchNbaSlate } from '~/api/nba'
import { fetchNflCurrentWeek } from '~/api/nfl'
import { fetchNhlSlate } from '~/api/nhl'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'
import { parseSlateDate } from '~/utils/slateDates'

/**
 * The queries the home page prefetches (`homePrefetch`), kept apart from the sport hooks so the
 * prefetch chunk loads without their other dependencies. The hooks re-export these: one definition
 * of each key.
 */

type SlatePage<M> = (params: { date?: string, tour?: string }) => Promise<{ matches: M[] }>

/** One stored UTC date of a tennis slate. */
export function tennisSlateQuery<M>(kind: 'today' | 'best-picks', fetchPage: SlatePage<M>, date: string, tour?: string) {
  return {
    queryKey: ['tennis', kind, { date, tour }],
    queryFn: () => fetchPage({ date, tour }),
    staleTime: SLATE_STALE_MS,
    retry: 2,
  }
}

export function nflCurrentWeekQuery() {
  return queryOptions({
    queryKey: ['nfl', 'current-week'],
    queryFn: fetchNflCurrentWeek,
    staleTime: 60 * 60 * 1000,
  })
}

/** A null or impossible date asks the API for its default slate; `enabled: false` waits, e.g. until a game page knows its date. */
export function nbaSlateQuery(date: string | null, enabled = true) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nba', 'slate', requested],
    queryFn: enabled ? () => fetchNbaSlate(requested) : skipToken,
    staleTime: SLATE_STALE_MS,
  })
}

/** A null date asks the API for its default slate; `enabled: false` waits, e.g. until a game page knows its date. */
export function nhlSlateQuery(date: string | null, enabled = true) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'slate', requested],
    queryFn: enabled ? () => fetchNhlSlate(requested) : skipToken,
    staleTime: SLATE_STALE_MS,
  })
}
