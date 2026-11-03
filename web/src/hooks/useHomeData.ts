import { useEffect, useMemo, useState } from 'react'
import { useModelPredictions } from '~/hooks/useModelTrackRecord'
import { useNbaModelRanking, useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import { useNflCurrentWeek, useNflSlate } from '~/hooks/useNfl'
import { useNflModelRanking } from '~/hooks/useNflModelTrackRecord'
import { useNhlSlate } from '~/hooks/useNhl'
import { useTennisToday } from '~/hooks/useTennisToday'
import { chooseLead, stripOrder, stripRow, type HomeSportData, type HomeStatus, type StripRow } from '~/utils/home'
import { rankingRecord, tennisRecord, type HomeRecord } from '~/utils/homeRecords'
import { nbaSource, nflSource, nhlSource, tennisSource, type HomeSource } from '~/utils/homeSources'
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
  lead: Sport | null
  strip: (StripRow & { retry: () => void })[]
  /** Published model records for the sports that have a model page, in registry order. */
  records: HomeRecord[]
  /** True until any sport has answered, so the page shows one loading state rather than four. */
  loading: boolean
  /** True when every sport failed. */
  failed: boolean
}

const EMPTY_SOURCE: HomeSource = { gameCount: 0, startsMs: [], propLines: null, gaps: [], nextGames: [], period: null }

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
  const nbaGaps = useNbaSlateGaps(nba.data?.date ?? null)
  const nhl = useNhlSlate(null)
  const tennis = useTennisToday()
  const tennisModel = useModelPredictions()
  const nflRanking = useNflModelRanking(week.data?.season ?? null)
  const nbaRanking = useNbaModelRanking()

  const nfl = useMemo<HomeSource>(() => {
    if (!nflSlate.data) return EMPTY_SOURCE
    // Built as of now, so only games not yet kicked off reach the digest.
    const digest = slateDigest(buildNflPropBoard(nflSlate.data.games, 'all', new Date(now)))
    return nflSource(nflSlate.data, digest, now)
  }, [nflSlate.data, now])
  // A failed gap list only hides the table; the games still count.
  const nbaSourceValue = useMemo<HomeSource>(() => nba.data
    ? nbaSource(nba.data.games, nbaSlateDigest(nbaGaps.data?.items ?? []), now)
    : EMPTY_SOURCE, [nba.data, nbaGaps.data, now])
  const nhlSourceValue = useMemo<HomeSource>(() => nhl.data ? nhlSource(nhl.data.games, now) : EMPTY_SOURCE, [nhl.data, now])
  const tennisSourceValue = useMemo<HomeSource>(
    () => tennis.data ? tennisSource(tennis.data.matches, now) : EMPTY_SOURCE,
    [tennis.data, now],
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
  const lead = chooseLead(data, now)
  const strip = stripOrder(data, lead, now).map(entry => ({
    ...stripRow(entry, now),
    retry: sports.find(sport => sport.data.sport === entry.sport)!.retry,
  }))
  return {
    now,
    sports,
    lead,
    strip,
    records: [
      tennisRecord(tennisModel.data, statusOf(tennisModel)),
      rankingRecord('nfl', nflRanking.data, week.isError || nflRanking.isError ? 'error' : 'loading'),
      rankingRecord('nba', nbaRanking.data, statusOf(nbaRanking)),
    ],
    loading: data.every(entry => entry.status === 'loading'),
    failed: data.every(entry => entry.status === 'error'),
  }
}
