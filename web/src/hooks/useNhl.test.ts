import { QueryClient, QueryObserver } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fetchNhlGame, fetchNhlLineOnlyProps, fetchNhlSlate } from '~/api/nhl'
import { nhlGameQuery, nhlLineOnlyPropsQuery, nhlSlateQuery } from '~/hooks/useNhl'

vi.mock('~/api/nhl', () => ({
  fetchNhlGame: vi.fn(async (gameId: number) => ({ gameId })),
  fetchNhlLineOnlyProps: vi.fn(async (gameId: number) => ({ gameId, lines: [] })),
  fetchNhlSlate: vi.fn(async (date: string | null) => ({ date, games: [] })),
}))

let cache: QueryClient

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-23T12:00:00Z'))
  cache = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } })
})

afterEach(() => {
  cache.clear()
  vi.useRealTimers()
})

it.each([null, 0, -1, NaN, Infinity, 1.5, Number.MAX_SAFE_INTEGER + 1])('invalid id %s never starts detail or props fetching', gameId => {
  const detail = new QueryObserver(cache, nhlGameQuery(gameId))
  const props = new QueryObserver(cache, nhlLineOnlyPropsQuery(gameId))
  const unsubscribeDetail = detail.subscribe(() => undefined)
  const unsubscribeProps = props.subscribe(() => undefined)
  expect(detail.getCurrentResult().fetchStatus).toBe('idle')
  expect(props.getCurrentResult().fetchStatus).toBe('idle')
  expect(fetchNhlGame).not.toHaveBeenCalled()
  expect(fetchNhlLineOnlyProps).not.toHaveBeenCalled()
  unsubscribeDetail()
  unsubscribeProps()
})

it('isolates game and prop caches by id and keeps the five-minute freshness boundary', async () => {
  await cache.fetchQuery(nhlGameQuery(7))
  await cache.fetchQuery(nhlGameQuery(8))
  await cache.fetchQuery(nhlLineOnlyPropsQuery(7))
  expect(fetchNhlGame).toHaveBeenCalledTimes(2)
  expect(fetchNhlLineOnlyProps).toHaveBeenCalledTimes(1)
  expect(cache.getQueryData(['nhl', 'game', 7])).toEqual({ gameId: 7 })
  expect(cache.getQueryData(['nhl', 'game', 8])).toEqual({ gameId: 8 })
  expect(cache.getQueryData(['nhl', 'game', 7, 'line-only-props'])).toEqual({ gameId: 7, lines: [] })
  vi.advanceTimersByTime(299_999)
  await cache.fetchQuery(nhlGameQuery(7))
  await cache.fetchQuery(nhlLineOnlyPropsQuery(7))
  expect(fetchNhlGame).toHaveBeenCalledTimes(2)
  expect(fetchNhlLineOnlyProps).toHaveBeenCalledTimes(1)
  vi.advanceTimersByTime(2)
  await cache.fetchQuery(nhlGameQuery(7))
  await cache.fetchQuery(nhlLineOnlyPropsQuery(7))
  expect(fetchNhlGame).toHaveBeenCalledTimes(3)
  expect(fetchNhlLineOnlyProps).toHaveBeenCalledTimes(2)
})

it('normalizes malformed dates to the server default and separates explicit dates', async () => {
  await cache.fetchQuery(nhlSlateQuery('2026-02-29'))
  await cache.fetchQuery(nhlSlateQuery(null))
  expect(fetchNhlSlate).toHaveBeenCalledExactlyOnceWith(null)
  await cache.fetchQuery(nhlSlateQuery('2026-10-23'))
  await cache.fetchQuery(nhlSlateQuery('2026-10-24'))
  expect(fetchNhlSlate).toHaveBeenCalledTimes(3)
  expect(cache.getQueryData(['nhl', 'slate', '2026-10-23'])).toEqual({ date: '2026-10-23', games: [] })
  vi.advanceTimersByTime(300_001)
  await cache.fetchQuery(nhlSlateQuery('2026-10-23'))
  expect(fetchNhlSlate).toHaveBeenCalledTimes(4)
})
