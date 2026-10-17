import { useQueries } from '@tanstack/react-query'
import { fetchPredictionsToday } from '~/api/tennis'
import { utcDatesForCentralDay } from '~/utils/tennisDates'

function getTodayStr() {
  return new Date().toISOString().split('T')[0]
}

function getTomorrowStr() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().split('T')[0]
}

export function useTennisToday(params?: { date?: string; tour?: string }) {
  const today = getTodayStr()
  const tomorrow = getTomorrowStr()

  const dates = params?.date ? utcDatesForCentralDay(params.date) : [today, tomorrow]
  const baseQueries = dates.map(date => ({
    queryKey: ['tennis', 'today', { date, tour: params?.tour }],
    queryFn: () => fetchPredictionsToday({ date, tour: params?.tour }),
  }))

  const results = useQueries({
    queries: baseQueries.map(q => ({ ...q, staleTime: 5 * 60 * 1000, retry: 2 })),
  })

  const isLoading = results.some(q => q.isLoading)
  const isError = results.some(q => q.isError)
  const error = results.find(q => q.error)?.error ?? null
  const allMatches = results.flatMap(q => q.data?.matches ?? [])

  return {
    data: results.some(q => q.data != null) ? {
      date: params?.date ?? today,
      count: allMatches.length,
      matches: allMatches,
    } : undefined,
    isLoading,
    isError,
    error,
    refetch: () => results.forEach(q => q.refetch()),
    isSuccess: results.every(q => q.isSuccess),
  }
}
