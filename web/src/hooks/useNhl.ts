import { queryOptions, skipToken, useQuery } from '@tanstack/react-query'
import { fetchNhlGame, fetchNhlLineOnlyProps, fetchNhlModelRanking, fetchNhlPlayerProps, fetchNhlPropBoard, fetchNhlSlate } from '~/api/nhl'
import type { PropRankingRecord } from '~/types/propRanking'
import { retryUnlessNotFound } from '~/utils/httpError'
import { validNhlGameId, validNhlPlayerId } from '~/utils/nhlGame'
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

export function nhlPlayerPropsQuery(playerId: number | null, date: string | null) {
  const id = validNhlPlayerId(playerId) ? playerId : null
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'player', id, 'props', requested],
    queryFn: id === null ? skipToken : () => fetchNhlPlayerProps(id, requested),
    staleTime: STALE_TIME,
    retry: retryUnlessNotFound,
  })
}

export function nhlPropBoardQuery(date: string | null) {
  const requested = parseSlateDate(date)
  return queryOptions({
    queryKey: ['nhl', 'prop-board', requested],
    queryFn: () => fetchNhlPropBoard(requested),
    staleTime: STALE_TIME,
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

export function useNhlPlayerProps(playerId: number | null, date: string | null) {
  return useQuery(nhlPlayerPropsQuery(playerId, date))
}

export function useNhlPropBoard(date: string | null) {
  return useQuery(nhlPropBoardQuery(date))
}

export function useNhlModelRanking() {
  return useQuery<PropRankingRecord, Error>({
    queryKey: ['nhl', 'model', 'ranking', { season: 'current' }],
    queryFn: fetchNhlModelRanking,
    // The API caches the check for 15 minutes, so refetching sooner gains nothing.
    staleTime: 15 * 60 * 1000,
    retry: retryUnlessNotFound,
  })
}
