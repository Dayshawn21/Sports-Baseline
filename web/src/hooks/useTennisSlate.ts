import { useQueries } from '@tanstack/react-query'
import { defaultSlateDates, utcDatesForCentralDay } from '~/utils/tennisDates'

interface SlateParams {
  date?: string
  tour?: string
  /** Central days to load together, when no single date is set (the tennis slate's default day). */
  days?: string[]
}

function slateUtcDates(params: SlateParams | undefined, defaults: [string, string]): string[] {
  if (params?.date) return utcDatesForCentralDay(params.date)
  if (params?.days?.length) return [...new Set(params.days.flatMap(utcDatesForCentralDay))]
  return defaults
}

/** One query per stored UTC date of the slate, merged into a single match list. */
export function useTennisSlate<M>(
  kind: 'today' | 'best-picks',
  fetchPage: (params: { date?: string, tour?: string }) => Promise<{ matches: M[] }>,
  params?: SlateParams,
) {
  const defaults = defaultSlateDates(new Date())
  const dates = slateUtcDates(params, defaults)
  const results = useQueries({
    queries: dates.map(date => ({
      queryKey: ['tennis', kind, { date, tour: params?.tour }],
      queryFn: () => fetchPage({ date, tour: params?.tour }),
      staleTime: 5 * 60 * 1000,
      retry: 2,
    })),
  })

  const allMatches = results.flatMap(q => q.data?.matches ?? [])
  return {
    data: results.some(q => q.data != null) ? {
      date: params?.date ?? params?.days?.[0] ?? defaults[0],
      count: allMatches.length,
      matches: allMatches,
    } : undefined,
    isLoading: results.some(q => q.isLoading),
    isError: results.some(q => q.isError),
    error: results.find(q => q.error)?.error ?? null,
    refetch: () => results.forEach(q => q.refetch()),
    isSuccess: results.every(q => q.isSuccess),
    dataUpdatedAt: Math.max(0, ...results.map(q => q.dataUpdatedAt)),
  }
}
