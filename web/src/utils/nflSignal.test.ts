import { describe, expect, it } from 'vitest'
import { allowedLabel, edgeLabel, edgePctLabel, overProbabilityLabel, overShareLabel, signalSummary, trustLabel } from '~/utils/nflSignal'

describe('edgeLabel', () => {
  it('signs the edge and keeps one decimal', () => {
    expect(edgeLabel(12.34)).toBe('+12.3')
    expect(edgeLabel(-2)).toBe('-2.0')
    expect(edgeLabel(0)).toBe('0.0')
  })

  it('marks a missing edge', () => {
    expect(edgeLabel(null)).toBe('--')
  })
})

describe('edgePctLabel', () => {
  it('renders a fraction as a signed percent', () => {
    expect(edgePctLabel(0.132)).toBe('+13.2%')
    expect(edgePctLabel(-0.05)).toBe('-5.0%')
    expect(edgePctLabel(null)).toBe('--')
  })
})

describe('trustLabel', () => {
  it('calls a stale baseline out for review', () => {
    expect(trustLabel({ qualityFlags: ['stale_baseline_season'] })).toBe('Review')
  })

  it('watches a row with any non-routine flag', () => {
    expect(trustLabel({ qualityFlags: ['historical_baseline', 'recent_market_model', 'small_sample'] })).toBe('Watch')
    expect(trustLabel({ qualityFlags: ['historical_baseline', 'injury_questionable'] })).toBe('Watch')
  })

  it('reads ready when only the routine method flags are present', () => {
    expect(trustLabel({ qualityFlags: [] })).toBe('Ready')
    expect(trustLabel({ qualityFlags: ['historical_baseline', 'recent_market_model', 'opponent_adjusted', 'usage_adjusted'] })).toBe('Ready')
  })
})

describe('signalSummary', () => {
  const base = {
    edge: 10,
    gamesInSample: 8,
    line: 60,
    market: 'receiving_yards',
    opponentAdjustmentPct: null,
    opponentAllowedHistory: { average: 74, values: [] },
    opponentTeam: 'BUF',
    position: 'WR',
    projection: 70,
    qualityFlags: [],
    recentForm: { average: 66, values: [{ value: 66, opponentTeam: 'MIA' }] },
    usageAdjustmentPct: null,
  }

  it('summarizes the model comparison and available recent and matchup stats', () => {
    expect(signalSummary(base)).toBe('Model 70.0 vs 60.0 line · Recent 66.0 avg (1g) · BUF allowed WRs 74.0/g')
  })

  it('includes material usage and matchup adjustments after the stats', () => {
    expect(signalSummary({ ...base, usageAdjustmentPct: 4, opponentAdjustmentPct: -6 })).toContain('Usage +4.0% · Matchup -6.0%')
  })

  it('formats Anytime TD model and recent form as probabilities', () => {
    expect(signalSummary({ ...base, market: 'anytime_touchdown', projection: 0.46, line: 0.5, recentForm: { average: 0.4, values: [] }, opponentAllowedHistory: { average: 0.5, values: [] } })).toBe('Model 46.0% vs 50.0% line · Recent 40.0% avg (0g) · BUF allowed a TD to WRs in 50.0% of games')
  })

  it('reports when there is nothing to compare', () => {
    expect(signalSummary({ ...base, gamesInSample: 0, projection: null, line: null, recentForm: { average: null, values: [] }, opponentAllowedHistory: { average: null, values: [] } })).toBe('Market comparison unavailable')
  })
})

describe('allowedLabel', () => {
  const row = { market: 'receiving_yards', opponentAllowedHistory: { average: 160, values: [] }, opponentTeam: 'BUF', position: 'WR' }

  it('reads as a position-group total per game', () => {
    expect(allowedLabel(row)).toBe('BUF allowed WRs 160.0/g')
  })

  it('falls back when the position or opponent is unknown', () => {
    expect(allowedLabel({ ...row, position: null, opponentTeam: null })).toBe('Opponent allowed the position 160.0/g')
  })

  it('is absent without allowed history', () => {
    expect(allowedLabel({ ...row, opponentAllowedHistory: { average: null, values: [] } })).toBeNull()
  })
})

describe('overProbabilityLabel', () => {
  it('shows the over and under split as whole percents', () => {
    expect(overProbabilityLabel({ pOver: 0.4449, pUnder: 0.5551 })).toBe('Over 44% · Under 56%')
  })

  it('is null where the fit is not shown', () => {
    expect(overProbabilityLabel({ pOver: null, pUnder: null })).toBeNull()
  })
})

describe('overShareLabel', () => {
  it('labels an alternative line by its over chance', () => {
    expect(overShareLabel(0.708)).toBe('71% over')
    expect(overShareLabel(null)).toBeNull()
  })
})
