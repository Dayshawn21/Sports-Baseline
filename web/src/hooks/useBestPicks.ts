import { fetchBestPicks } from '~/api/tennis'
import { useTennisSlate } from '~/hooks/useTennisSlate'

export function useBestPicks(params?: { date?: string; tour?: string; days?: string[] }) {
  return useTennisSlate('best-picks', fetchBestPicks, params)
}
