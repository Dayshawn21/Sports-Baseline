import type { QueryClient } from '@tanstack/react-query'
import { fetchPredictionsToday } from '~/api/tennis'
import { nbaSlateQuery, nflCurrentWeekQuery, nhlSlateQuery, tennisSlateQuery } from '~/hooks/homeQueries'
import { defaultSlateDates } from '~/utils/tennisDates'

/**
 * Starts the home page's first queries before React renders it. They otherwise wait
 * for the lazy HomePage chunk and its first render: 0.9 s observed, about 4.6 s under
 * Lighthouse's mobile throttling (2026-11-23). Same options as the hooks, so the hooks
 * join these requests instead of sending their own; a failure is left for them to show.
 */
export function prefetchHome(queryClient: QueryClient, now: Date): void {
  // Tennis first: its card's next match is the page's largest paint.
  for (const date of defaultSlateDates(now)) {
    void queryClient.prefetchQuery(tennisSlateQuery('today', fetchPredictionsToday, date))
  }
  void queryClient.prefetchQuery(nflCurrentWeekQuery())
  void queryClient.prefetchQuery(nbaSlateQuery(null))
  void queryClient.prefetchQuery(nhlSlateQuery(null))
}
