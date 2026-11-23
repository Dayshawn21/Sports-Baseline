import { queryOptions, skipToken, useQuery } from '@tanstack/react-query'
import { fetchNflGame, fetchNflGameContext, fetchNflGameNotes, fetchNflHomeSlate, fetchNflLineOnlyProps, fetchNflOtherMarkets, fetchNflPlayer, fetchNflSlate, fetchNflWeekLineOnlyProps } from '~/api/nfl'
import { retryUnlessNotFound } from '~/utils/httpError'
import { SLATE_STALE_MS } from '~/hooks/queryTimes'
import { nflCurrentWeekQuery } from '~/hooks/homeQueries'

export { nflCurrentWeekQuery }

export function nflSlateQuery(season: number | null, week: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'slate', season, week],
    queryFn: season === null || week === null ? skipToken : () => fetchNflSlate(season, week),
    staleTime: SLATE_STALE_MS,
  })
}

export function nflHomeSlateQuery(season: number | null, week: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'slate', 'home', { season, week }],
    queryFn: season === null || week === null ? skipToken : () => fetchNflHomeSlate(season, week),
    staleTime: SLATE_STALE_MS,
  })
}

export function nflGameNotesQuery(season: number | null, week: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'game-notes', season, week],
    queryFn: season === null || week === null ? skipToken : () => fetchNflGameNotes(season, week),
    staleTime: SLATE_STALE_MS,
  })
}

export function nflPlayerQuery(playerId: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'player', playerId],
    queryFn: playerId === null ? skipToken : () => fetchNflPlayer(playerId),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nflLineOnlyPropsQuery(gameId: number) {
  return queryOptions({
    queryKey: ['nfl', 'game', gameId, 'line-only'],
    queryFn: () => fetchNflLineOnlyProps(gameId),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nflOtherMarketsQuery(playerId: number | null, season: number | null, week: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'other-markets', { playerId, season, week }],
    queryFn: playerId === null || season === null || week === null ? skipToken : () => fetchNflOtherMarkets(playerId, season, week),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nflWeekLineOnlyPropsQuery(season: number | null, week: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'line-only', season, week],
    queryFn: season === null || week === null ? skipToken : () => fetchNflWeekLineOnlyProps(season, week),
    staleTime: SLATE_STALE_MS,
  })
}

export function nflGameQuery(gameId: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'game', gameId],
    queryFn: gameId === null ? skipToken : () => fetchNflGame(gameId),
    staleTime: SLATE_STALE_MS,
    retry: retryUnlessNotFound,
  })
}

export function nflGameContextQuery(gameId: number | null) {
  return queryOptions({
    queryKey: ['nfl', 'game', gameId, 'context'],
    queryFn: gameId === null || !Number.isSafeInteger(gameId) || gameId <= 0 ? skipToken : () => fetchNflGameContext(gameId),
    staleTime: SLATE_STALE_MS,
    retry: false,
  })
}

export function useNflSlate(season: number | null, week: number | null) {
  return useQuery(nflSlateQuery(season, week))
}

export function useNflHomeSlate(season: number | null, week: number | null) {
  return useQuery(nflHomeSlateQuery(season, week))
}

export function useNflGameNotes(season: number | null, week: number | null) {
  return useQuery(nflGameNotesQuery(season, week))
}

export function useNflCurrentWeek() {
  return useQuery(nflCurrentWeekQuery())
}

export function useNflPlayer(playerId: number | null) {
  return useQuery(nflPlayerQuery(playerId))
}

export function useNflLineOnlyProps(gameId: number) {
  return useQuery(nflLineOnlyPropsQuery(gameId))
}

export function useNflOtherMarkets(playerId: number | null, season: number | null, week: number | null) {
  return useQuery(nflOtherMarketsQuery(playerId, season, week))
}

export function useNflWeekLineOnlyProps(season: number | null, week: number | null) {
  return useQuery(nflWeekLineOnlyPropsQuery(season, week))
}

export function useNflGame(gameId: number | null) {
  return useQuery(nflGameQuery(gameId))
}

export function useNflGameContext(gameId: number | null) {
  return useQuery(nflGameContextQuery(gameId))
}
