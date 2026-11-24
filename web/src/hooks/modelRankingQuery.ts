import { queryOptions } from '@tanstack/react-query'
import { fetchNbaModelRanking } from '~/api/nba'
import { fetchNhlModelRanking } from '~/api/nhl'
import type { PropRankingRecord } from '~/types/propRanking'
import { retryUnlessNotFound } from '~/utils/httpError'
import { TRACK_RECORD_STALE_MS } from '~/hooks/queryTimes'

export function modelRankingQuery(sport: 'nba' | 'nhl') {
  return queryOptions<PropRankingRecord, Error>({
    queryKey: [sport, 'model', 'ranking', { season: 'current' }],
    queryFn: sport === 'nba' ? fetchNbaModelRanking : fetchNhlModelRanking,
    staleTime: TRACK_RECORD_STALE_MS,
    retry: retryUnlessNotFound,
  })
}
