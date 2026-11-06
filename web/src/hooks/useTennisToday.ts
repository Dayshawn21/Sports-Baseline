import { fetchPredictionsToday } from '~/api/tennis'
import { useTennisSlate } from '~/hooks/useTennisSlate'

export function useTennisToday(params?: { date?: string; tour?: string }) {
  return useTennisSlate('today', fetchPredictionsToday, params)
}
