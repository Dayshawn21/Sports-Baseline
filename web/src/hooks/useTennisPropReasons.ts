import { useQuery } from '@tanstack/react-query'
import { fetchTennisPropReasons } from '~/api/tennis'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'

/** Fetched only while the row's panel is open, so the board load is unchanged. */
export function useTennisPropReasons(propId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['tennis', 'prop-reasons', { propId }],
    queryFn: () => fetchTennisPropReasons(propId),
    enabled,
    staleTime: SLATE_STALE_MS,
    retry: 1,
  })
}
