import { QueryClient, QueryObserver, type QueryKey, type QueryObserverOptions } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fetchNbaGame, fetchNbaLineOnlyProps, fetchNbaPlayerProps, fetchNbaPropBoard, fetchNbaProps, fetchNbaSlate, fetchNbaSlateGaps } from '~/api/nba'
import { nbaGameQuery, nbaLineOnlyPropsQuery, nbaPlayerPropsQuery, nbaPropBoardQuery, nbaPropsQuery, nbaSlateGapsQuery, nbaSlateQuery } from '~/hooks/useNba'

vi.mock('~/api/nba', () => ({
  fetchNbaGame: vi.fn(async (gameId: number) => ({ gameId })),
  fetchNbaLineOnlyProps: vi.fn(async (gameId: number) => ({ gameId, lines: [] })),
  fetchNbaProps: vi.fn(async (gameId: number) => ({ gameId, markets: [] })),
  fetchNbaPlayerProps: vi.fn(async (playerId: number, date: string | null) => ({ playerId, date, markets: [] })),
  fetchNbaPropBoard: vi.fn(async (date: string | null) => ({ date, markets: [] })),
  fetchNbaSlate: vi.fn(async (date: string | null) => ({ date, games: [] })),
  fetchNbaSlateGaps: vi.fn(async (date: string, limit?: number) => ({ date, limit, items: [] })),
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

it('a missing id never starts game, props or player fetching', () => {
  expect(staysIdle(nbaGameQuery(null))).toBe(true)
  expect(staysIdle(nbaLineOnlyPropsQuery(null))).toBe(true)
  expect(staysIdle(nbaPropsQuery(null))).toBe(true)
  expect(staysIdle(nbaPlayerPropsQuery(null, '2026-11-16'))).toBe(true)
  expect(fetchNbaGame).not.toHaveBeenCalled()
  expect(fetchNbaLineOnlyProps).not.toHaveBeenCalled()
  expect(fetchNbaProps).not.toHaveBeenCalled()
  expect(fetchNbaPlayerProps).not.toHaveBeenCalled()
})

it('a disabled slate and gaps without a date wait', () => {
  expect(staysIdle(nbaSlateQuery('2026-11-16', false))).toBe(true)
  expect(staysIdle(nbaSlateGapsQuery(null))).toBe(true)
  expect(staysIdle(nbaSlateGapsQuery('2026-02-30'))).toBe(true)
  expect(fetchNbaSlate).not.toHaveBeenCalled()
  expect(fetchNbaSlateGaps).not.toHaveBeenCalled()
})

it('an impossible date shares the default slate and board entries', async () => {
  await cache.fetchQuery(nbaSlateQuery('2026-02-30'))
  await cache.fetchQuery(nbaSlateQuery(null))
  expect(fetchNbaSlate).toHaveBeenCalledExactlyOnceWith(null)
  await cache.fetchQuery(nbaPropBoardQuery('2026-02-30'))
  await cache.fetchQuery(nbaPropBoardQuery(null))
  expect(fetchNbaPropBoard).toHaveBeenCalledExactlyOnceWith(null)
  await cache.fetchQuery(nbaPlayerPropsQuery(7, '2026-02-30'))
  await cache.fetchQuery(nbaPlayerPropsQuery(7, null))
  expect(fetchNbaPlayerProps).toHaveBeenCalledExactlyOnceWith(7, null)
})

it('valid dates keep their existing keys', async () => {
  await cache.fetchQuery(nbaSlateQuery('2026-11-16'))
  await cache.fetchQuery(nbaSlateGapsQuery('2026-11-16'))
  await cache.fetchQuery(nbaSlateGapsQuery('2026-11-16', 3))
  await cache.fetchQuery(nbaPlayerPropsQuery(7, '2026-11-16'))
  expect(cache.getQueryData(['nba', 'slate', '2026-11-16'])).toEqual({ date: '2026-11-16', games: [] })
  expect(cache.getQueryData(['nba', 'slate', '2026-11-16', 'gaps'])).toEqual({ date: '2026-11-16', limit: undefined, items: [] })
  expect(cache.getQueryData(['nba', 'slate', '2026-11-16', 'gaps', { limit: 3 }])).toEqual({ date: '2026-11-16', limit: 3, items: [] })
  expect(cache.getQueryData(['nba', 'player', 7, 'props', '2026-11-16'])).toEqual({ playerId: 7, date: '2026-11-16', markets: [] })
})

it('isolates game caches by id and keeps the five-minute freshness boundary', async () => {
  await cache.fetchQuery(nbaGameQuery(7))
  await cache.fetchQuery(nbaGameQuery(8))
  await cache.fetchQuery(nbaPropsQuery(7))
  expect(fetchNbaGame).toHaveBeenCalledTimes(2)
  expect(cache.getQueryData(['nba', 'game', 7])).toEqual({ gameId: 7 })
  expect(cache.getQueryData(['nba', 'game', 7, 'props'])).toEqual({ gameId: 7, markets: [] })
  vi.advanceTimersByTime(299_999)
  await cache.fetchQuery(nbaGameQuery(7))
  expect(fetchNbaGame).toHaveBeenCalledTimes(2)
  vi.advanceTimersByTime(2)
  await cache.fetchQuery(nbaGameQuery(7))
  expect(fetchNbaGame).toHaveBeenCalledTimes(3)
})
