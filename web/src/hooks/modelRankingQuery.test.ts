import { describe, expect, it } from 'vitest'
import { fetchNbaModelRanking } from '~/api/nba'
import { fetchNhlModelRanking } from '~/api/nhl'
import { modelRankingQuery } from '~/hooks/modelRankingQuery'
import { TRACK_RECORD_STALE_MS } from '~/hooks/queryTimes'

describe('modelRankingQuery', () => {
  it('keeps each sport on its own key and fetcher', () => {
    expect(modelRankingQuery('nba').queryKey).toEqual(['nba', 'model', 'ranking', { season: 'current' }])
    expect(modelRankingQuery('nhl').queryKey).toEqual(['nhl', 'model', 'ranking', { season: 'current' }])
    expect(modelRankingQuery('nba').queryFn).toBe(fetchNbaModelRanking)
    expect(modelRankingQuery('nhl').queryFn).toBe(fetchNhlModelRanking)
  })

  it('refetches no sooner than the API cache', () => {
    expect(modelRankingQuery('nba').staleTime).toBe(TRACK_RECORD_STALE_MS)
  })
})
