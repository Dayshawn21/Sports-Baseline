import { QueryClient, QueryObserver, type QueryKey, type QueryObserverOptions } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fetchNflGame, fetchNflGameContext, fetchNflGameNotes, fetchNflOtherMarkets, fetchNflPlayer, fetchNflSlate, fetchNflWeekLineOnlyProps } from '~/api/nfl'
import { nflGameContextQuery, nflGameNotesQuery, nflGameQuery, nflOtherMarketsQuery, nflPlayerQuery, nflSlateQuery, nflWeekLineOnlyPropsQuery } from '~/hooks/useNfl'

vi.mock('~/api/nfl', () => ({
  fetchNflCurrentWeek: vi.fn(async () => ({ season: 2026, week: 11 })),
  fetchNflGame: vi.fn(async (gameId: number) => ({ gameId })),
  fetchNflGameContext: vi.fn(async (gameId: number) => ({ gameId })),
  fetchNflGameNotes: vi.fn(async (season: number, week: number) => ({ season, week, notes: [] })),
  fetchNflLineOnlyProps: vi.fn(async (gameId: number) => ({ gameId, lines: [] })),
  fetchNflOtherMarkets: vi.fn(async (playerId: number, season: number, week: number) => ({ playerId, season, week })),
  fetchNflPlayer: vi.fn(async (playerId: number) => ({ playerId })),
  fetchNflSlate: vi.fn(async (season: number, week: number) => ({ season, week, games: [] })),
  fetchNflWeekLineOnlyProps: vi.fn(async (season: number, week: number) => ({ season, week, lines: [] })),
}))

let cache: QueryClient

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-16T12:00:00Z'))
  cache = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } })
})

afterEach(() => {
  cache.clear()
  vi.useRealTimers()
})

function staysIdle<T, E, K extends QueryKey>(options: QueryObserverOptions<T, E, T, T, K>) {
  const observer = new QueryObserver(cache, options)
  const unsubscribe = observer.subscribe(() => undefined)
  const status = observer.getCurrentResult().fetchStatus
  unsubscribe()
  return status === 'idle'
}

it.each([[null, 11], [2026, null], [null, null]])('season %s week %s never starts a week fetch', (season, week) => {
  expect(staysIdle(nflSlateQuery(season, week))).toBe(true)
  expect(staysIdle(nflGameNotesQuery(season, week))).toBe(true)
  expect(staysIdle(nflWeekLineOnlyPropsQuery(season, week))).toBe(true)
  expect(staysIdle(nflOtherMarketsQuery(7, season, week))).toBe(true)
  expect(fetchNflSlate).not.toHaveBeenCalled()
  expect(fetchNflGameNotes).not.toHaveBeenCalled()
  expect(fetchNflWeekLineOnlyProps).not.toHaveBeenCalled()
  expect(fetchNflOtherMarkets).not.toHaveBeenCalled()
})

it('a missing player or game id never fetches', () => {
  expect(staysIdle(nflPlayerQuery(null))).toBe(true)
  expect(staysIdle(nflOtherMarketsQuery(null, 2026, 11))).toBe(true)
  expect(staysIdle(nflGameQuery(null))).toBe(true)
  expect(fetchNflPlayer).not.toHaveBeenCalled()
  expect(fetchNflGame).not.toHaveBeenCalled()
})

it.each([null, 0, -1, NaN, 1.5, Number.MAX_SAFE_INTEGER + 1])('game context skips invalid id %s', gameId => {
  expect(staysIdle(nflGameContextQuery(gameId))).toBe(true)
  expect(fetchNflGameContext).not.toHaveBeenCalled()
})

it('keys each week and id on its own entry', async () => {
  await cache.fetchQuery(nflSlateQuery(2026, 11))
  await cache.fetchQuery(nflSlateQuery(2026, 12))
  await cache.fetchQuery(nflOtherMarketsQuery(7, 2026, 11))
  await cache.fetchQuery(nflGameContextQuery(9))
  expect(fetchNflSlate).toHaveBeenCalledTimes(2)
  expect(cache.getQueryData(['nfl', 'slate', 2026, 11])).toEqual({ season: 2026, week: 11, games: [] })
  expect(cache.getQueryData(['nfl', 'other-markets', { playerId: 7, season: 2026, week: 11 }])).toEqual({ playerId: 7, season: 2026, week: 11 })
  expect(cache.getQueryData(['nfl', 'game', 9, 'context'])).toEqual({ gameId: 9 })
})

it('keeps the five-minute freshness boundary', async () => {
  await cache.fetchQuery(nflGameQuery(7))
  vi.advanceTimersByTime(299_999)
  await cache.fetchQuery(nflGameQuery(7))
  expect(fetchNflGame).toHaveBeenCalledTimes(1)
  vi.advanceTimersByTime(2)
  await cache.fetchQuery(nflGameQuery(7))
  expect(fetchNflGame).toHaveBeenCalledTimes(2)
})
