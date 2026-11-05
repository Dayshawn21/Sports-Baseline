import { useEffect, useMemo, useState } from 'react'
import { useModelPredictions } from '~/hooks/useModelTrackRecord'
import { useNbaModelRanking, useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import { useNflCurrentWeek, useNflSlate } from '~/hooks/useNfl'
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
  /** True until any sport has answered, so the page shows one loading state rather than four. */
  loading: boolean
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
  const nflSlate = useNflSlate(week.data?.season ?? null, week.data?.week ?? null)
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

  const nflStatus: HomeStatus = week.isError ? 'error' : week.isPending ? 'loading' : statusOf(nflSlate)
  const tennisStatus: HomeStatus = tennis.isError && !tennis.data ? 'error' : tennis.isLoading ? 'loading' : 'ready'
  const sports = [
    homeSport('nfl', nflStatus, nfl, () => { void week.refetch(); void nflSlate.refetch() }),
    homeSport('nba', statusOf(nba), nbaSourceValue, () => void nba.refetch()),
    homeSport('nhl', statusOf(nhl), nhlSourceValue, () => void nhl.refetch()),
    homeSport('tennis', tennisStatus, tennisSourceValue, () => tennis.refetch()),
  ]

  const data = sports.map(sport => sport.data)
  return {
    now,
    sports,
    cards: sports.map(sport => ({ ...homeCard(sport.data, sport.source, now), retry: sport.retry })),
    refreshedAt: newestUpdate([nflSlate.dataUpdatedAt, nba.dataUpdatedAt, nhl.dataUpdatedAt, tennis.dataUpdatedAt]),
    records: [
      tennisRecord(tennisModel.data, statusOf(tennisModel)),
      rankingRecord('nfl', nflRanking.data, week.isError || nflRanking.isError ? 'error' : 'loading'),
      rankingRecord('nba', nbaRanking.data, statusOf(nbaRanking)),
      rankingRecord('nhl', nhlRanking.data, statusOf(nhlRanking)),
    ],
    loading: data.every(entry => entry.status === 'loading'),
    failed: data.every(entry => entry.status === 'error'),
  }
}
