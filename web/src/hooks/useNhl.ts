import { queryOptions, skipToken, useQuery } from '@tanstack/react-query'
import { fetchNhlGame, fetchNhlLineOnlyProps, fetchNhlSlate } from '~/api/nhl'
import { retryUnlessNotFound } from '~/utils/httpError'
import { validNhlGameId } from '~/utils/nhlGame'
import { parseSlateDate } from '~/utils/slateDates'

const STALE_TIME = 5 * 60 * 1000

export function nhlSlateQuery(date: string | null) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'slate', requested],
    queryFn: () => fetchNhlSlate(requested),
    staleTime: STALE_TIME,
  })
}

export function nhlGameQuery(gameId: number | null) {
  const id = validNhlGameId(gameId) ? gameId : null
  return queryOptions({
    queryKey: ['nhl', 'game', id],
    queryFn: id === null ? skipToken : () => fetchNhlGame(id),
    staleTime: STALE_TIME,
    retry: retryUnlessNotFound,
  })
}

export function nhlLineOnlyPropsQuery(gameId: number | null) {
  const id = validNhlGameId(gameId) ? gameId : null
  return queryOptions({
    queryKey: ['nhl', 'game', id, 'line-only-props'],
    queryFn: id === null ? skipToken : () => fetchNhlLineOnlyProps(id),
    staleTime: STALE_TIME,
    retry: retryUnlessNotFound,
  })
}

export function useNhlSlate(date: string | null) {
  return useQuery(nhlSlateQuery(date))
}

export function useNhlGame(gameId: number | null) {
  return useQuery(nhlGameQuery(gameId))
}

export function useNhlLineOnlyProps(gameId: number | null) {
  return useQuery(nhlLineOnlyPropsQuery(gameId))
}
