import { describe, expect, it } from 'vitest'
import type { NflClvMarket, NflClvRow, NflModelClv, NflModelRanking, NflRankingSlice } from '~/types/nfl'
import { signedPoints, sliceLabel, sliceProgress, summaryCounts, verdictLabel } from '~/utils/nflTrackRecord'

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
