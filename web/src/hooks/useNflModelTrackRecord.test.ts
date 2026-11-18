import { QueryClient, QueryObserver, type QueryKey, type QueryObserverOptions } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fetchNflModelClv, fetchNflModelPropLines, fetchNflModelRanking } from '~/api/nfl'
import { nflModelClvQuery, nflModelPropLinesQuery, nflModelRankingQuery } from '~/hooks/useNflModelTrackRecord'

vi.mock('~/api/nfl', () => ({
  fetchNflModelClv: vi.fn(async (season: number) => ({ season, kind: 'clv' })),
  fetchNflModelFit: vi.fn(async () => ({})),
  fetchNflModelPropLines: vi.fn(async (season: number) => ({ season, kind: 'lines' })),
  fetchNflModelRanking: vi.fn(async (season: number, modelVersion?: string) => ({ season, modelVersion })),
}))

let cache: QueryClient

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-18T12:00:00Z'))
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

it('a missing season never fetches', () => {
  expect(staysIdle(nflModelRankingQuery(null))).toBe(true)
  expect(staysIdle(nflModelPropLinesQuery(null))).toBe(true)
  expect(staysIdle(nflModelClvQuery(null))).toBe(true)
  expect(fetchNflModelRanking).not.toHaveBeenCalled()
  expect(fetchNflModelPropLines).not.toHaveBeenCalled()
  expect(fetchNflModelClv).not.toHaveBeenCalled()
})

it('fetches each season under the existing cache keys', async () => {
  await cache.fetchQuery(nflModelRankingQuery(2026, 'nfl-targets-v1'))
  await cache.fetchQuery(nflModelPropLinesQuery(2026))
  await cache.fetchQuery(nflModelClvQuery(2026))
  expect(fetchNflModelRanking).toHaveBeenCalledWith(2026, 'nfl-targets-v1')
  expect(cache.getQueryData(['nfl', 'model', 'ranking', { season: 2026, modelVersion: 'nfl-targets-v1' }]))
    .toEqual({ season: 2026, modelVersion: 'nfl-targets-v1' })
  expect(cache.getQueryData(['nfl', 'model', 'prop-lines', { season: 2026 }])).toEqual({ season: 2026, kind: 'lines' })
  expect(cache.getQueryData(['nfl', 'model', 'game-line-clv', { season: 2026 }])).toEqual({ season: 2026, kind: 'clv' })
})
