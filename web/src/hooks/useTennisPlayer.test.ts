import { QueryClient, QueryObserver } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fetchPlayerStats } from '~/api/tennis'
import { playerStatsQuery } from '~/hooks/useTennisPlayer'

vi.mock('~/api/tennis', () => ({
  fetchPlayerStats: vi.fn(async (name: string) => ({ name })),
}))

let cache: QueryClient

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-11-06T12:00:00Z'))
  cache = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } })
})

afterEach(() => {
  cache.clear()
  vi.useRealTimers()
})

it('rebuilt options for the same player share one request', async () => {
  const observers = Array.from({ length: 5 }, () => new QueryObserver(cache, playerStatsQuery('Jannik Sinner', 'ATP', 'Hard')))
  const unsubscribe = observers.map((observer) => observer.subscribe(() => undefined))
  await vi.runAllTimersAsync()
  expect(fetchPlayerStats).toHaveBeenCalledExactlyOnceWith('Jannik Sinner', 'ATP', 'Hard')
  unsubscribe.forEach((stop) => stop())
})

it('separates players, tours and surfaces, and treats missing tour or surface as null', async () => {
  await cache.fetchQuery(playerStatsQuery('Jannik Sinner', 'ATP', 'Hard'))
  await cache.fetchQuery(playerStatsQuery('Jannik Sinner', 'ATP', 'Clay'))
  await cache.fetchQuery(playerStatsQuery('Carlos Alcaraz', 'ATP', 'Hard'))
  await cache.fetchQuery(playerStatsQuery('Iga Swiatek'))
  await cache.fetchQuery(playerStatsQuery('Iga Swiatek', null, null))
  expect(fetchPlayerStats).toHaveBeenCalledTimes(4)
  expect(fetchPlayerStats).toHaveBeenLastCalledWith('Iga Swiatek', null, null)
  expect(cache.getQueryData(['tennis', 'player-stats', { name: 'Iga Swiatek', tour: null, surface: null }])).toEqual({ name: 'Iga Swiatek' })
})

it('keeps stats fresh for five minutes', async () => {
  await cache.fetchQuery(playerStatsQuery('Jannik Sinner', 'ATP', 'Hard'))
  vi.advanceTimersByTime(299_999)
  await cache.fetchQuery(playerStatsQuery('Jannik Sinner', 'ATP', 'Hard'))
  expect(fetchPlayerStats).toHaveBeenCalledTimes(1)
  vi.advanceTimersByTime(2)
  await cache.fetchQuery(playerStatsQuery('Jannik Sinner', 'ATP', 'Hard'))
  expect(fetchPlayerStats).toHaveBeenCalledTimes(2)
})
