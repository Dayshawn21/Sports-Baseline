import type { QueryClient } from '@tanstack/react-query'
import { nbaPropBoardQuery } from '~/hooks/useNba'
import { nhlPropBoardQuery } from '~/hooks/useNhl'
import type { BoardPrefetchTarget } from '~/utils/boardRoute'

/**
 * Starts a props board request while its lazy page chunk loads; it otherwise waited for the
 * page to mount (F-45). Same query options as the page, so the page joins this request.
 */
export function prefetchBoard(queryClient: QueryClient, { sport, date }: BoardPrefetchTarget): void {
  if (sport === 'nba') void queryClient.prefetchQuery(nbaPropBoardQuery(date))
  else void queryClient.prefetchQuery(nhlPropBoardQuery(date))
}
