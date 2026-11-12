import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import type { ModelPropTiersResponse } from '~/types/tennis'
import type { HomeStatus } from '~/utils/home'
import { SPORTS, type Sport } from '~/utils/sportNav'

export interface BoardRecordTally {
  wins: number
  losses: number
  hitRate: number
  /** Pick-weighted break-even, so a goblin-heavy pool is not judged against the standard one. */
  baseline: number
}

export interface BoardRecordSegment {
  kind: 'dropped' | 'retired'
  label: string
  tally: BoardRecordTally | null
}

/** The prop board's record strip; always reference, so it carries no signal color. */
export interface BoardRecord {
  status: HomeStatus
  version: string | null
  graded: BoardRecordTally | null
  note: string | null
  liveSlices: number
  adoptedSlices: number
  /** Dropped and retired records, never folded into `graded`. */
  setAside: BoardRecordSegment[]
  modelPath: string
}

/** A strip query's state; a refetch error over loaded data keeps the data, as the Model pages do. */
export function recordStatus(query: { isError: boolean, isPending: boolean, data?: unknown }): HomeStatus {
  if (query.data !== undefined) return 'ready'
  return query.isError ? 'error' : query.isPending ? 'loading' : 'error'
}

export const NO_GRADED_PICKS = 'No graded picks yet'

/** Mirrors `PROJECTION_VERSION` in `api/app/services/tennis/prop_snapshots.py`; no tennis props response carries it. */
export const TENNIS_PROP_VERSION = 'props-v3'
export const TENNIS_CHECK_NOT_RUN = 'Forward check not run yet'

function modelPath(sport: Sport): string {
  return SPORTS.find(entry => entry.code === sport)!.views.model
}

function tally(slices: readonly PropRankingSlice[]): BoardRecordTally | null {
  const picks = slices.reduce((total, slice) => total + slice.n, 0)
  if (picks === 0) return null
  const wins = slices.reduce((total, slice) => total + slice.hits, 0)
  const baseline = slices.reduce((total, slice) => total + slice.breakEven * slice.n, 0) / picks
  return { wins, losses: picks - wins, hitRate: wins / picks, baseline }
}

function emptyRecord(sport: Sport, status: HomeStatus): BoardRecord {
  return { status, version: null, graded: null, note: null, liveSlices: 0, adoptedSlices: 0, setAside: [], modelPath: modelPath(sport) }
}

/** NFL, NBA and NHL: a rejected slice is final for its version, so it is counted as dropped, apart from the live W-L. */
export function rankingBoardRecord(
  sport: 'nfl' | 'nba' | 'nhl',
  ranking: PropRankingRecord<string | null> | undefined,
  status: HomeStatus,
): BoardRecord {
  if (!ranking) return emptyRecord(sport, status)
  const dropped = ranking.slices.filter(slice => slice.verdict === 'reject')
  const live = ranking.slices.filter(slice => slice.verdict !== 'reject')
  const graded = tally(live)
  const setAside: BoardRecordSegment[] = dropped.length === 0 ? [] : [{
    kind: 'dropped',
    label: `${dropped.length} ${dropped.length === 1 ? 'slice' : 'slices'} dropped`,
    tally: tally(dropped),
  }]
  return {
    status: 'ready',
    version: ranking.modelVersion,
    graded,
    note: graded ? null : NO_GRADED_PICKS,
    liveSlices: live.length,
    adoptedSlices: live.filter(slice => slice.verdict === 'adopt').length,
    setAside,
    modelPath: modelPath(sport),
  }
}

/** Tennis serves no props-v3 grading yet (48e has not run), so the strip shows the retired props-v2 tier record beside it. */
export function tennisBoardRecord(tiers: ModelPropTiersResponse | undefined, status: HomeStatus): BoardRecord {
  if (!tiers) return emptyRecord('tennis', status)
  const decided = tiers.tiers.reduce((total, tier) => total + tier.decided, 0)
  const wins = tiers.tiers.reduce((total, tier) => total + tier.hits, 0)
  return {
    status: 'ready',
    version: TENNIS_PROP_VERSION,
    graded: null,
    note: TENNIS_CHECK_NOT_RUN,
    liveSlices: 0,
    adoptedSlices: 0,
    setAside: [{
      kind: 'retired',
      label: `Retired: tiers (${tiers.projectionVersion})`,
      tally: decided === 0 ? null : { wins, losses: decided - wins, hitRate: wins / decided, baseline: tiers.breakEven },
    }],
    modelPath: modelPath('tennis'),
  }
}

function percent(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`
}

/** "260-140 · 65.0% vs 65.0% break-even": a W-L means nothing without the rate it has to beat. */
export function tallyText(tally: BoardRecordTally): string {
  return `${tally.wins}-${tally.losses} · ${percent(tally.hitRate)} vs ${percent(tally.baseline)} break-even`
}
