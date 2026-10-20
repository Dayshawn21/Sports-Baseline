import { describe, expect, it } from 'vitest'
import type { NflClvMarket, NflClvRow, NflModelClv, NflModelRanking, NflRankingSlice } from '~/types/nfl'
import {
  NFL_TARGETS_RANKING_MODEL, NFL_V4_RANKING_MODEL, rankingParams, rankingPresentation, rankingQueryKey,
  rankingSliceStatus, signedPoints, sliceLabel, sliceProgress, summaryCounts, verdictLabel,
} from '~/utils/nflTrackRecord'

function slice(verdict: NflRankingSlice['verdict']): NflRankingSlice {
  return {
    oddsType: 'standard', side: 'over', verdict, n: 30, weeks: 1, hits: 16,
    hitRate: 0.533, standardError: 0.091, breakEven: 0.577, signal: 'neutral',
  }
}

function ranking(verdicts: NflRankingSlice['verdict'][], lastSettledWeek: number | null = 3): NflModelRanking {
  return {
    gradedAt: '2026-09-30T12:00:00Z', season: 2026, modelVersion: 'v4', overProbabilityVersion: 'nfl-pover-v1',
    rule: { minPicks: 200, minWeeks: 4, minPickMargin: 0.03 },
    finishedWeeks: lastSettledWeek === null ? [] : [lastSettledWeek], lastSettledWeek,
    frozenRows: 0, excluded: {}, coverage: [], funnel: { calls: 0, withPOver: 0, picks: 0, bets: 0 },
    slices: verdicts.map(slice),
  }
}

const ROW: NflClvRow = { n: 0, meanClv: null, standardError: null, toward: 0, away: 0, flat: 0, wins: 0, losses: 0, pushes: 0 }

function clv(verdicts: NflClvMarket['verdict'][]): NflModelClv {
  return {
    gradedAt: '2026-09-30T12:00:00Z', season: 2026, rule: { pickThreshold: 1.5, verdictPicks: 150 },
    markets: verdicts.map((verdict, i) => ({
      market: i === 0 ? 'spread' : 'total', modelVersion: 'nfl-elo-v1', graded: 0, excluded: {},
      medianLeadHours: null, minLeadHours: null, verdict, verdictWeeks: [],
      headline: ROW, all: ROW, early: ROW, late: ROW, signal: 'neutral',
    })),
  }
}

describe('sliceLabel and verdictLabel', () => {
  it('names a slice by its payout and side', () => {
    expect(sliceLabel('standard', 'under')).toBe('Standard under')
    expect(sliceLabel('demon', 'over')).toBe('Demon over')
  })

  it('reads both rules\' still-filling states as Accruing', () => {
    expect(verdictLabel('insufficient')).toBe('Accruing')
    expect(verdictLabel('accruing')).toBe('Accruing')
    expect(verdictLabel('adopt')).toBe('Adopt')
    expect(verdictLabel('pass')).toBe('Pass')
    expect(verdictLabel('reject')).toBe('Reject')
  })
})

describe('sliceProgress', () => {
  it('shows whichever of picks and weeks is further behind', () => {
    expect(sliceProgress(62, 1, 200, 4)).toBeCloseTo(0.25)
    expect(sliceProgress(200, 1, 200, 4)).toBeCloseTo(0.25)
    expect(sliceProgress(30, 4, 200, 4)).toBeCloseTo(0.15)
  })

  it('is full only when both are met, and never past full', () => {
    expect(sliceProgress(240, 5, 200, 4)).toBe(1)
    expect(sliceProgress(0, 0, 200, 4)).toBe(0)
  })
})

describe('summaryCounts', () => {
  it('keeps a targets record out of the v4 summary while retaining the CLV figures', () => {
    const targets = { ...ranking(['adopt'], 6), modelVersion: NFL_TARGETS_RANKING_MODEL, overProbabilityVersion: null }
    expect(summaryCounts(targets, clv(['pass']))).toEqual({
      slicesAdopted: '\u2014', gameLineVerdicts: '1 of 1', gameLinePasses: '1 passed', lastSettledWeek: '\u2014',
    })
  })
  it('counts adopted slices, decided and passed game-line verdicts, and the last settled week', () => {
    const counts = summaryCounts(
      ranking(['adopt', 'insufficient', 'reject', 'insufficient']),
      clv(['pass', 'accruing']),
    )

    expect(counts).toEqual({
      slicesAdopted: '1 of 4', gameLineVerdicts: '1 of 2', gameLinePasses: '1 passed', lastSettledWeek: 'W3',
    })
  })

  it('waits on each section on its own', () => {
    expect(summaryCounts(undefined, undefined)).toEqual({
      slicesAdopted: '—', gameLineVerdicts: '—', gameLinePasses: '', lastSettledWeek: '—',
    })
    expect(summaryCounts(ranking([], null), undefined).lastSettledWeek).toBe('None yet')
    expect(summaryCounts(undefined, clv(['accruing', 'accruing'])).gameLineVerdicts).toBe('0 of 2')
  })
})

describe('model-specific ranking queries', () => {
  it('canonicalizes omitted and explicit v4 selectors, and separates targets and seasons', () => {
    expect(rankingParams(2026)).toEqual({ season: 2026 })
    expect(rankingParams(2026, NFL_V4_RANKING_MODEL)).toEqual({ season: 2026 })
    expect(rankingParams(2026, NFL_TARGETS_RANKING_MODEL)).toEqual({ season: 2026, model_version: 'nfl-targets-v1' })
    expect(rankingQueryKey(2026)).toEqual(rankingQueryKey(2026, NFL_V4_RANKING_MODEL))
    expect(rankingQueryKey(2026)).not.toEqual(rankingQueryKey(2026, NFL_TARGETS_RANKING_MODEL))
    expect(rankingQueryKey(2026, NFL_TARGETS_RANKING_MODEL)).not.toEqual(rankingQueryKey(2027, NFL_TARGETS_RANKING_MODEL))
    expect(rankingQueryKey(null)).not.toEqual(rankingQueryKey(2026))
  })
})

describe('reference ranking presentation', () => {
  const standard = slice('insufficient')
  const record: NflModelRanking = {
    ...ranking([]), modelVersion: NFL_TARGETS_RANKING_MODEL, overProbabilityVersion: null,
    slices: [standard, { ...standard, side: 'under' }, { ...standard, oddsType: 'goblin' }, { ...standard, oddsType: 'demon' }],
  }

  it('shows only supported reference slices and labels a null probability version truthfully', () => {
    const view = rankingPresentation(record, true)
    expect(view.slices.map((s) => sliceLabel(s.oddsType, s.side))).toEqual(['Standard over', 'Standard under'])
    expect(view.probabilityVersion).toBe('Not served')
    expect(view.empty).toBe(true)
    expect(rankingPresentation({ ...record, frozenRows: 12 }, true).empty).toBe(false)
  })

  it('keeps reference status neutral and explains why zero picks do not accrue', () => {
    expect(rankingSliceStatus({ ...standard, verdict: 'adopt', signal: 'positive' }, true)).toEqual({
      label: 'Not accruing', signal: 'neutral', noPicks: 'No probability picks',
    })
  })

  it('preserves all slices, probability versions and signal labels for default v4/NBA rendering', () => {
    const named = { ...record, overProbabilityVersion: 'nba-pover-v1' }
    const view = rankingPresentation(named)
    expect(view.slices).toBe(named.slices)
    expect(view.probabilityVersion).toBe('nba-pover-v1')
    expect(rankingSliceStatus({ ...standard, verdict: 'adopt', signal: 'positive' })).toEqual({
      label: 'Adopt', signal: 'positive', noPicks: 'No picks yet',
    })
    expect(rankingSliceStatus(standard).label).toBe('Accruing')
  })
})

describe('signedPoints', () => {
  it('signs positive CLV and keeps two places', () => {
    expect(signedPoints(0.4211)).toBe('+0.42')
    expect(signedPoints(-0.17)).toBe('-0.17')
    expect(signedPoints(0)).toBe('0.00')
  })

  it('shows a dash for a missing value', () => {
    expect(signedPoints(null)).toBe('—')
  })
})
