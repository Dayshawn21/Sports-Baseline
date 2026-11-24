import { useCallback, useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useModelPredictions } from '~/hooks/useModelTrackRecord'
import { useNbaModelRanking, useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import { useNflCurrentWeek, useNflHomeSlate } from '~/hooks/useNfl'
import { useNflModelRanking } from '~/hooks/useNflModelTrackRecord'
import { useNhlModelRanking, useNhlSlate } from '~/hooks/useNhl'
import { usePrizePicksProps } from '~/hooks/useProps'
import { useTennisToday } from '~/hooks/useTennisToday'
import { homeCard, newestUpdate, type HomeCard, type HomeSportData, type HomeStatus } from '~/utils/home'
import { rankingRecord, tennisRecord, type HomeRecord } from '~/utils/homeRecords'
import { GAPS_PER_SPORT, nbaSource, nflSource, nhlSource, tennisSource, type HomeSource } from '~/utils/homeSources'
import { nbaSlateDigest } from '~/utils/nbaSlate'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { slateDigest } from '~/utils/nflSlate'
import type { Sport } from '~/utils/sportNav'

const CLOCK_TICK_MS = 60 * 1000

export interface HomeSport {
  data: HomeSportData
  source: HomeSource
  retry: () => void
}

export interface HomeView {
  now: number
  sports: HomeSport[]
  /** One card per sport in the fixed order NFL, NBA, NHL, Tennis. */
  cards: (HomeCard & { retry: () => void })[]
  /** When the newest slate loaded; null until one has. */
  refreshedAt: number | null
  /** Published model records for the sports that have a model page, in registry order. */
  records: HomeRecord[]
  /** True when every sport failed. */
  failed: boolean
}

const EMPTY_SOURCE: HomeSource = { gameCount: 0, startsMs: [], propLines: null, gaps: [], moneyline: [], nextGames: [], schedule: [], period: null, days: [] }

function statusOf(query: { isError: boolean, isPending: boolean }): HomeStatus {
  if (query.isError) return 'error'
  return query.isPending ? 'loading' : 'ready'
}

function homeSport(sport: Sport, status: HomeStatus, source: HomeSource, retry: () => void): HomeSport {
  return { data: { sport, status, gameCount: source.gameCount, startsMs: source.startsMs }, source, retry }
}

function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), CLOCK_TICK_MS)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

/** Today across sports, from the queries the sport pages already make (same keys, so a slate opens from cache). */
export function useHomeData(): HomeView {
  const now = useNow()
  const week = useNflCurrentWeek()
  // The full week is 14 MB; the home page needs only its standard full-game lines.
  const nflSlate = useNflHomeSlate(week.data?.season ?? null, week.data?.week ?? null)
  const nba = useNbaSlate(null)
  const nbaGaps = useNbaSlateGaps(nba.data?.date ?? null, GAPS_PER_SPORT)
  const nhl = useNhlSlate(null)
  const tennis = useTennisToday()
  const tennisProps = usePrizePicksProps()
  const tennisModel = useModelPredictions()
  const nflRanking = useNflModelRanking(week.data?.season ?? null)
  const nbaRanking = useNbaModelRanking()
  const nhlRanking = useNhlModelRanking()

  const nfl = useMemo<HomeSource>(() => {
    if (!nflSlate.data) return EMPTY_SOURCE
    // Built as of now, so only games not yet kicked off reach the digest.
    const digest = slateDigest(buildNflPropBoard(nflSlate.data.games, 'all', new Date(now)), GAPS_PER_SPORT)
    return nflSource(nflSlate.data, digest, now)
  }, [nflSlate.data, now])
  // A failed gap list only hides the table; the games still count.
  const nbaSourceValue = useMemo<HomeSource>(() => nba.data
    ? { ...nbaSource(nba.data.games, nbaSlateDigest(nbaGaps.data?.items ?? []), nba.data.date, now), gapsFailed: nbaGaps.isError }
    : EMPTY_SOURCE, [nba.data, nbaGaps.data, nbaGaps.isError, now])
  const nhlSourceValue = useMemo<HomeSource>(() => nhl.data ? nhlSource(nhl.data.games, now) : EMPTY_SOURCE, [nhl.data, now])
  const tennisSourceValue = useMemo<HomeSource>(
    () => tennis.data
      ? { ...tennisSource(tennis.data.matches, now, tennisProps.data?.props ?? []), gapsFailed: tennisProps.isError }
      : EMPTY_SOURCE,
    [tennis.data, tennisProps.data, tennisProps.isError, now],
  )

  // Each query landing re-renders this hook; every value below changes only with its own inputs, so the
  // memoized home sections skip the renders their data did not cause (548 Link renders on 2026-11-23).
  const queryClient = useQueryClient()
  const { refetch: refetchWeek } = week
  const { refetch: refetchNfl } = nflSlate
  const { refetch: refetchNba } = nba
  const { refetch: refetchNhl } = nhl
  const retryNfl = useCallback(() => { void refetchWeek(); void refetchNfl() }, [refetchWeek, refetchNfl])
  const retryNba = useCallback(() => void refetchNba(), [refetchNba])
  const retryNhl = useCallback(() => void refetchNhl(), [refetchNhl])
  // useTennisToday builds its refetch per render; these are the queries it would refetch.
  const retryTennis = useCallback(
    () => void queryClient.refetchQueries({ queryKey: ['tennis', 'today'], type: 'active' }),
    [queryClient],
  )

  const nflStatus: HomeStatus = week.isError ? 'error' : week.isPending ? 'loading' : statusOf(nflSlate)
  const nbaStatus = statusOf(nba)
  const nhlStatus = statusOf(nhl)
  const tennisStatus: HomeStatus = tennis.isError && !tennis.data ? 'error' : tennis.isLoading ? 'loading' : 'ready'
  const nflSport = useMemo(() => homeSport('nfl', nflStatus, nfl, retryNfl), [nflStatus, nfl, retryNfl])
  const nbaSport = useMemo(() => homeSport('nba', nbaStatus, nbaSourceValue, retryNba), [nbaStatus, nbaSourceValue, retryNba])
  const nhlSport = useMemo(() => homeSport('nhl', nhlStatus, nhlSourceValue, retryNhl), [nhlStatus, nhlSourceValue, retryNhl])
  const tennisSport = useMemo(
    () => homeSport('tennis', tennisStatus, tennisSourceValue, retryTennis),
    [tennisStatus, tennisSourceValue, retryTennis],
  )
  const sports = useMemo(() => [nflSport, nbaSport, nhlSport, tennisSport], [nflSport, nbaSport, nhlSport, tennisSport])

  const nflCard = useHomeCard(nflSport, now)
  const nbaCard = useHomeCard(nbaSport, now)
  const nhlCard = useHomeCard(nhlSport, now)
  const tennisCard = useHomeCard(tennisSport, now)
  const cards = useMemo(() => [nflCard, nbaCard, nhlCard, tennisCard], [nflCard, nbaCard, nhlCard, tennisCard])

  const tennisModelStatus = statusOf(tennisModel)
  const nflRankingStatus: HomeStatus = week.isError || nflRanking.isError ? 'error' : 'loading'
  const nbaRankingStatus = statusOf(nbaRanking)
  const nhlRankingStatus = statusOf(nhlRanking)
  const records = useMemo(() => [
    tennisRecord(tennisModel.data, tennisModelStatus),
    rankingRecord('nfl', nflRanking.data, nflRankingStatus),
    rankingRecord('nba', nbaRanking.data, nbaRankingStatus),
    rankingRecord('nhl', nhlRanking.data, nhlRankingStatus),
  ], [tennisModel.data, tennisModelStatus, nflRanking.data, nflRankingStatus, nbaRanking.data, nbaRankingStatus, nhlRanking.data, nhlRankingStatus])

  return {
    now,
    sports,
    cards,
    refreshedAt: newestUpdate([nflSlate.dataUpdatedAt, nba.dataUpdatedAt, nhl.dataUpdatedAt, tennis.dataUpdatedAt]),
    records,
    failed: sports.every(sport => sport.data.status === 'error'),
  }
}

function useHomeCard(sport: HomeSport, now: number): HomeCard & { retry: () => void } {
  return useMemo(() => ({ ...homeCard(sport.data, sport.source, now), retry: sport.retry }), [sport, now])
}
