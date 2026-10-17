import { describe, expect, it } from 'vitest'
import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import { nbaModelSummary } from '~/utils/nbaModel'

function slice(verdict: PropRankingSlice['verdict']): PropRankingSlice {
  return {
    oddsType: 'standard', side: 'over', verdict, n: 0, weeks: 0, hits: 0,
    hitRate: null, standardError: null, breakEven: 0.577, signal: 'neutral',
  }
}

function ranking(verdicts: PropRankingSlice['verdict'][], lastSettledWeek: number | null): PropRankingRecord {
  return {
    gradedAt: '2026-10-07T21:00:00Z', season: 2026, modelVersion: 'nba-reference-v1', overProbabilityVersion: 'nba-pover-v1',
    rule: { minPicks: 200, minWeeks: 4, minPickMargin: 0.03 },
    finishedWeeks: lastSettledWeek === null ? [] : [lastSettledWeek], lastSettledWeek,
    frozenRows: 0, excluded: {}, coverage: [], funnel: { calls: 0, withPOver: 0, picks: 0, bets: 0 },
    slices: verdicts.map(slice),
  }
}

describe('nbaModelSummary', () => {
  it('shows a placeholder for every figure until the check loads', () => {
    expect(nbaModelSummary(undefined)).toEqual({
      slicesAdopted: '—', lastSettledWeek: '—', projectionVersion: '—', overProbabilityVersion: '—',
    })
  })

  it('reads none yet before the first week settles', () => {
    const summary = nbaModelSummary(ranking(['insufficient', 'insufficient', 'insufficient', 'insufficient'], null))

    expect(summary).toEqual({
      slicesAdopted: '0 of 4', lastSettledWeek: 'None yet',
      projectionVersion: 'nba-reference-v1', overProbabilityVersion: 'nba-pover-v1',
    })
  })

  it('counts only adopted slices, not rejected ones', () => {
    const summary = nbaModelSummary(ranking(['adopt', 'reject', 'insufficient', 'insufficient'], 5))

    expect(summary.slicesAdopted).toBe('1 of 4')
    expect(summary.lastSettledWeek).toBe('W5')
  })
})
