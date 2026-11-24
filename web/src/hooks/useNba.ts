import { queryOptions, skipToken, useQuery } from '@tanstack/react-query'
import { fetchNbaGame, fetchNbaLineOnlyProps, fetchNbaPlayerProps, fetchNbaPropBoard, fetchNbaProps, fetchNbaSlateGaps } from '~/api/nba'
import { retryUnlessNotFound } from '~/utils/httpError'
import { modelRankingQuery } from '~/hooks/modelRankingQuery'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'
import { nbaSlateQuery } from '~/hooks/homeQueries'
import { parseSlateDate } from '~/utils/slateDates'

export { nbaSlateQuery }

export function nbaPropBoardQuery(date: string | null) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nba', 'prop-board', requested],
    queryFn: () => fetchNbaPropBoard(requested),
    staleTime: SLATE_STALE_MS,
  })
}

/** The digest for a date the slate has already resolved; waits for it. */
export function nbaSlateGapsQuery(date: string | null, limit?: number) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: limit === undefined ? ['nba', 'slate', requested, 'gaps'] : ['nba', 'slate', requested, 'gaps', { limit }],
    queryFn: requested === null ? skipToken : () => fetchNbaSlateGaps(requested, limit),
    staleTime: SLATE_STALE_MS,
  })
}

export function nbaGameQuery(gameId: number | null) {
  return queryOptions({
    queryKey: ['nba', 'game', gameId],
    queryFn: gameId === null ? skipToken : () => fetchNbaGame(gameId),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nbaLineOnlyPropsQuery(gameId: number | null) {
  return queryOptions({
    queryKey: ['nba', 'game', gameId, 'line-only-props'],
    queryFn: gameId === null ? skipToken : () => fetchNbaLineOnlyProps(gameId),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nbaPropsQuery(gameId: number | null) {
  return queryOptions({
    queryKey: ['nba', 'game', gameId, 'props'],
    queryFn: gameId === null ? skipToken : () => fetchNbaProps(gameId),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nbaPlayerPropsQuery(playerId: number | null, date: string | null) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nba', 'player', playerId, 'props', requested],
    queryFn: playerId === null ? skipToken : () => fetchNbaPlayerProps(playerId, requested),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function useNbaSlate(date: string | null, enabled = true) {
  return useQuery(nbaSlateQuery(date, enabled))
}

export function useNbaPropBoard(date: string | null) {
  return useQuery(nbaPropBoardQuery(date))
}

export function useNbaSlateGaps(date: string | null, limit?: number) {
  return useQuery(nbaSlateGapsQuery(date, limit))
}

export function useNbaGame(gameId: number | null) {
  return useQuery(nbaGameQuery(gameId))
}

export function useNbaLineOnlyProps(gameId: number | null) {
  return useQuery(nbaLineOnlyPropsQuery(gameId))
}

export function useNbaProps(gameId: number | null) {
  return useQuery(nbaPropsQuery(gameId))
}

export function useNbaModelRanking() {
  return useQuery(modelRankingQuery('nba'))
}

export function useNbaPlayerProps(playerId: number | null, date: string | null) {
  return useQuery(nbaPlayerPropsQuery(playerId, date))
}
