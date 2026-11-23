import { QueryClient } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchNbaSlate } from '~/api/nba'
import { fetchNflCurrentWeek } from '~/api/nfl'
import { fetchNhlSlate } from '~/api/nhl'
import { fetchPredictionsToday } from '~/api/tennis'
import { prefetchHome } from '~/hooks/homePrefetch'
import { nbaSlateQuery } from '~/hooks/useNba'
import { nflCurrentWeekQuery } from '~/hooks/useNfl'
import { nhlSlateQuery } from '~/hooks/useNhl'
import { tennisSlateQuery } from '~/hooks/useTennisSlate'
import { isHomeRoute } from '~/utils/homeRoute'
import { defaultSlateDates } from '~/utils/tennisDates'

vi.mock('~/api/tennis', () => ({ fetchPredictionsToday: vi.fn(async () => ({ matches: [] })) }))
vi.mock('~/api/nfl', () => ({ fetchNflCurrentWeek: vi.fn(async () => ({ season: 2026, week: 11 })) }))
vi.mock('~/api/nba', () => ({ fetchNbaSlate: vi.fn(async () => ({ games: [] })) }))
vi.mock('~/api/nhl', () => ({ fetchNhlSlate: vi.fn(async () => ({ games: [] })) }))

const NOW = new Date('2026-11-23T01:00:00Z')
let cache: QueryClient

beforeEach(() => {
  vi.clearAllMocks()
  cache = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity, retry: false } } })
})

afterEach(() => cache.clear())

describe('isHomeRoute', () => {
  it.each(['', '#', '#/', '#/?tour=atp', '/'])('treats %j as the home page', hash => {
    expect(isHomeRoute(hash)).toBe(true)
  })

  it.each(['#/tennis', '#/nfl/game/1', '#/nba?date=2026-11-22', '#//'])('leaves %j alone', hash => {
    expect(isHomeRoute(hash)).toBe(false)
  })
})

describe('prefetchHome', () => {
  it("sends each home query once, which the hooks' own options then reuse", async () => {
    prefetchHome(cache, NOW)
    const [first, second] = defaultSlateDates(NOW)
    await Promise.all([
      cache.fetchQuery(tennisSlateQuery('today', fetchPredictionsToday, first)),
      cache.fetchQuery(tennisSlateQuery('today', fetchPredictionsToday, second)),
      cache.fetchQuery(nflCurrentWeekQuery()),
      cache.fetchQuery(nbaSlateQuery(null)),
      cache.fetchQuery(nhlSlateQuery(null)),
    ])

    expect(vi.mocked(fetchPredictionsToday).mock.calls).toEqual([[{ date: first }], [{ date: second }]])
    expect(fetchNflCurrentWeek).toHaveBeenCalledTimes(1)
    expect(fetchNbaSlate).toHaveBeenCalledTimes(1)
    expect(fetchNhlSlate).toHaveBeenCalledTimes(1)
  })

  it("keys the tennis dates exactly as the home page's useTennisToday() does", () => {
    prefetchHome(cache, NOW)

    const tennisKeys = cache.getQueryCache().getAll().map(query => query.queryKey).filter(key => key[0] === 'tennis')
    expect(tennisKeys).toEqual(defaultSlateDates(NOW).map(date => ['tennis', 'today', { date, tour: undefined }]))
  })
})
