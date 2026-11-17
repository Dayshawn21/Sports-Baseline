import { queryOptions, skipToken, useQuery } from '@tanstack/react-query'
import { fetchNhlGame, fetchNhlLineOnlyProps, fetchNhlPlayerProps, fetchNhlProjectionHistory, fetchNhlPropBoard, fetchNhlSlate } from '~/api/nhl'
import { retryUnlessNotFound } from '~/utils/httpError'
import { modelRankingQuery } from '~/hooks/modelRankingQuery'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'
import { validNhlGameId, validNhlPlayerId } from '~/utils/nhlGame'
import { parseSlateDate } from '~/utils/slateDates'

export function nhlSlateQuery(date: string | null) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'slate', requested],
    queryFn: () => fetchNhlSlate(requested),
    staleTime: SLATE_STALE_MS,
  })
}

export function nhlGameQuery(gameId: number | null) {
  const id = validNhlGameId(gameId) ? gameId : null
  return queryOptions({
    queryKey: ['nhl', 'game', id],
    queryFn: id === null ? skipToken : () => fetchNhlGame(id),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nhlLineOnlyPropsQuery(gameId: number | null) {
  const id = validNhlGameId(gameId) ? gameId : null
  return queryOptions({
    queryKey: ['nhl', 'game', id, 'line-only-props'],
    queryFn: id === null ? skipToken : () => fetchNhlLineOnlyProps(id),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nhlPlayerPropsQuery(playerId: number | null, date: string | null) {
  const id = validNhlPlayerId(playerId) ? playerId : null
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'player', id, 'props', requested],
    queryFn: id === null ? skipToken : () => fetchNhlPlayerProps(id, requested),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nhlProjectionHistoryQuery(playerId: number | null) {
  const id = validNhlPlayerId(playerId) ? playerId : null
  return queryOptions({
    queryKey: ['nhl', 'player', id, 'projection-history'],
    queryFn: id === null ? skipToken : () => fetchNhlProjectionHistory(id),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nhlPropBoardQuery(date: string | null) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'prop-board', requested],
    queryFn: () => fetchNhlPropBoard(requested),
    staleTime: SLATE_STALE_MS,
  })
}

/** A null date asks the API for its default slate; `enabled: false` waits, e.g. until a game page knows its date. */
export function useNhlSlate(date: string | null, enabled = true) {
  return useQuery({ ...nhlSlateQuery(date), enabled })
}

export function useNhlGame(gameId: number | null) {
  return useQuery(nhlGameQuery(gameId))
}

export function useNhlLineOnlyProps(gameId: number | null) {
  return useQuery(nhlLineOnlyPropsQuery(gameId))
}

export function useNhlPlayerProps(playerId: number | null, date: string | null) {
  return useQuery(nhlPlayerPropsQuery(playerId, date))
}

export function useNhlProjectionHistory(playerId: number | null) {
  return useQuery(nhlProjectionHistoryQuery(playerId))
}

export function useNhlPropBoard(date: string | null) {
  return useQuery(nhlPropBoardQuery(date))
}

export function useNhlModelRanking() {
  return useQuery(modelRankingQuery('nhl'))
}
