import { describe, expect, it } from 'vitest'
import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import type { ModelPropTiersResponse, TrackTierRow } from '~/types/tennis'
import { NO_GRADED_PICKS, rankingBoardRecord, recordStatus, tallyText, TENNIS_CHECK_NOT_RUN, tennisBoardRecord } from '~/utils/boardRecord'

function slice(overrides: Partial<PropRankingSlice>): PropRankingSlice {
  return {
    oddsType: 'standard', side: 'over', verdict: 'insufficient', n: 0, weeks: 0, hits: 0,
    hitRate: null, standardError: null, breakEven: 0.5774, signal: 'neutral', ...overrides,
  }
}

function ranking(slices: PropRankingSlice[], frozenRows = 100): PropRankingRecord<string | null> {
  return {
    gradedAt: '2026-11-11T12:00:00Z', season: 2025, modelVersion: 'nba-reference-v1', overProbabilityVersion: null,
    rule: { minPicks: 200, minWeeks: 4, minPickMargin: 0.02 }, finishedWeeks: [], lastSettledWeek: null,
    frozenRows, excluded: {}, coverage: [], funnel: { calls: 0, withPOver: 0, picks: 0, bets: 0 }, slices,
  }
}

describe('rankingBoardRecord', () => {
  it('keeps the loading and error states with no figures and the sport model link', () => {
    expect(rankingBoardRecord('nba', undefined, 'loading')).toEqual({
      status: 'loading', graded: null, note: null, liveSlices: 0, adoptedSlices: 0, setAside: [], modelPath: '/nba/model',
    })
    expect(rankingBoardRecord('nfl', undefined, 'error')).toMatchObject({ status: 'error', graded: null, modelPath: '/nfl/model' })
  })

  it('reads no graded picks when nothing is frozen or every slice is still empty', () => {
    const empty = rankingBoardRecord('nhl', ranking([], 0), 'ready')
    expect(empty).toMatchObject({ status: 'ready', graded: null, note: NO_GRADED_PICKS, liveSlices: 0 })
    const accruing = rankingBoardRecord('nhl', ranking([slice({}), slice({ side: 'under' }), slice({ oddsType: 'goblin' }), slice({ oddsType: 'demon' })]), 'ready')
    expect(accruing).toMatchObject({ graded: null, note: NO_GRADED_PICKS, liveSlices: 4, adoptedSlices: 0, setAside: [], modelPath: '/nhl/model' })
  })

  it('pools live slices against the pick-weighted break-even', () => {
    const record = rankingBoardRecord('nba', ranking([
      slice({ n: 100, hits: 60, breakEven: 0.5 }),
      slice({ oddsType: 'goblin', n: 300, hits: 200, breakEven: 0.7, verdict: 'adopt' }),
    ]), 'ready')
    // (100 x 0.5 + 300 x 0.7) / 400 = 0.65; 260 of 400 hit.
    expect(record.graded).toEqual({ wins: 260, losses: 140, hitRate: 0.65, baseline: 0.65 })
    expect(record).toMatchObject({ note: null, liveSlices: 2, adoptedSlices: 1, setAside: [] })
  })

  it('counts a rejected slice as dropped, apart from the live W-L', () => {
    const record = rankingBoardRecord('nfl', ranking([
      slice({ n: 50, hits: 30 }),
      slice({ oddsType: 'demon', n: 200, hits: 50, breakEven: 0.3, verdict: 'reject' }),
    ]), 'ready')
    expect(record.graded).toMatchObject({ wins: 30, losses: 20, hitRate: 0.6 })
    expect(record.graded?.baseline).toBeCloseTo(0.5774)
    expect(record.liveSlices).toBe(1)
    expect(record.setAside).toEqual([{ kind: 'dropped', label: '1 slice dropped', tally: { wins: 50, losses: 150, hitRate: 0.25, baseline: 0.3 } }])
  })

  it('shows every slice dropped with no live record', () => {
    const record = rankingBoardRecord('nfl', ranking([
      slice({ verdict: 'reject', n: 200, hits: 100, breakEven: 0.5 }),
      slice({ side: 'under', verdict: 'reject', n: 0, hits: 0 }),
    ]), 'ready')
    expect(record).toMatchObject({ graded: null, note: NO_GRADED_PICKS, liveSlices: 0 })
    expect(record.setAside).toEqual([{ kind: 'dropped', label: '2 slices dropped', tally: { wins: 100, losses: 100, hitRate: 0.5, baseline: 0.5 } }])
  })
})

describe('tallyText', () => {
  it('states the W-L with the hit rate and the break-even it has to beat, to one decimal', () => {
    expect(tallyText({ wins: 260, losses: 140, hitRate: 0.65, baseline: 0.65 })).toBe('260-140 · 65.0% vs 65.0% break-even')
    expect(tallyText({ wins: 1, losses: 2, hitRate: 1 / 3, baseline: 0.57735 })).toBe('1-2 · 33.3% vs 57.7% break-even')
  })
})

describe('recordStatus', () => {
  it('reads loaded data as ready even after a failed refetch, and otherwise error or loading', () => {
    expect(recordStatus({ isError: true, isPending: false, data: {} })).toBe('ready')
    expect(recordStatus({ isError: false, isPending: true })).toBe('loading')
    expect(recordStatus({ isError: true, isPending: false })).toBe('error')
  })
})

function tier(name: TrackTierRow['tier'], decided: number, hits: number): TrackTierRow {
  return {
    tier: name, decided, hits, pushes: 0, hitRate: decided ? hits / decided : null, standardError: null,
    verdict: 'reject', verdictSampleSize: decided, verdictHitRate: null, signal: 'neutral',
  }
}

function tiers(rows: TrackTierRow[]): ModelPropTiersResponse {
  return {
    gradedAt: '2026-11-11T12:00:00Z', projectionVersion: 'props-v2', verdictSample: 200, breakEven: 0.5774,
    excluded: { nonStandard: 0, awaiting: 0 }, tiers: rows, passSnapshotted: 0,
  }
}

describe('tennisBoardRecord', () => {
  it('keeps loading and error with no figures and the tennis model link', () => {
    expect(tennisBoardRecord(undefined, 'loading')).toMatchObject({ status: 'loading', setAside: [], modelPath: '/tennis/model' })
    expect(tennisBoardRecord(undefined, 'error')).toMatchObject({ status: 'error', graded: null })
  })

  it('shows no live record, and an empty retired record without a tally', () => {
    expect(tennisBoardRecord(tiers([tier('LOCK', 0, 0), tier('STRONG', 0, 0), tier('LEAN', 0, 0)]), 'ready')).toEqual({
      status: 'ready', graded: null, note: TENNIS_CHECK_NOT_RUN, liveSlices: 0, adoptedSlices: 0,
      setAside: [{ kind: 'retired', label: 'Retired tiers', tally: null }], modelPath: '/tennis/model',
    })
  })

  it('sums the three tiers into one retired W-L against the response break-even', () => {
    // 240 + 109 + 302 = 651 decided; 124 + 51 + 156 = 331 hits.
    const record = tennisBoardRecord(tiers([tier('LOCK', 240, 124), tier('STRONG', 109, 51), tier('LEAN', 302, 156)]), 'ready')
    expect(record.graded).toBeNull()
    expect(record.setAside).toEqual([{ kind: 'retired', label: 'Retired tiers', tally: { wins: 331, losses: 320, hitRate: 331 / 651, baseline: 0.5774 } }])
  })
})
