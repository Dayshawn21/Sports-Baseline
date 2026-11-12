import { useQuery } from '@tanstack/react-query'
import { fetchTennisPropReasons } from '~/api/tennis'

/** Fetched only while the row's panel is open, so the board load is unchanged. */
export function useTennisPropReasons(propId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['tennis', 'prop-reasons', { propId }],
    queryFn: () => fetchTennisPropReasons(propId),
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })
}
