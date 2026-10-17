import { describe, expect, it } from 'vitest'
import type { MatchBestPicks, MatchPrediction, RecentMatchResult } from '~/types/tennis'
import type { TennisBoardLine } from '~/utils/tennisPropBoard'
import { moneylineBoardRows, winASetBoardRows } from '~/utils/tennisPropBoard'
import { fantasyScore, propCard, recentStatBars, startLabel } from '~/utils/tennisPropCards'

function row(overrides: Partial<TennisBoardLine> = {}): TennisBoardLine {
  return {
    id: 7, playerId: 7, playerName: 'Ben Shelton', matchId: 10, source: 'prizepicks', statType: 'aces', line: '11.5', oddsType: 'standard',
    fetchedAt: '2026-09-28T10:00:00Z', startTime: '2026-09-29T05:10:00Z', pOver: null, pUnder: null, confidence: 'STRONG', recommendation: 'OVER',
    statAvg: 13.4, evPct: 14.4, hitProbability: 0.66, breakEvenPct: 57.7, matchesCount: 34, surface: 'Hard', opponentStatAvg: 0.61,
    dataQualityFlags: [], projectionStatus: 'ok', audit: { playerResolved: true, matchLinked: true, statsFresh: true, sampleSize: 34, opponentStatsFound: true, predictionFound: true, projectionFound: true },
    matchup: 'Ben Shelton vs Jakub Mensik', tournament: 'Tokyo', tour: 'ATP',
    ...overrides,
  }
}

const prediction: MatchPrediction = {
  matchId: 20, startUtc: '2026-09-29T03:00:00Z', p1Name: 'Billy Harris', p2Name: 'Felix Balshaw', tour: 'ATP', surface: 'Hard', tournament: 'Lima', round: 'R32',
  p1WinProb: 0.578, p2WinProb: 0.422, p1EloProb: null, p1MlProb: null, p1MarketProb: null, ensembleWeights: {}, qualityFlags: ['small_sample'],
  p1OddsAmerican: 129, p2OddsAmerican: -160, h2hP1Wins: 0, h2hP2Wins: 0,
}

function boardRow(line: ReturnType<typeof moneylineBoardRows>[number]): TennisBoardLine {
  return { ...line, matchup: null, tournament: null, tour: 'ATP' }
}

describe('propCard', () => {
  it('shows a standard prop the way the table cells did', () => {
    const card = propCard(row())
    expect(card).toMatchObject({
      key: 'prizepicks-7', playerName: 'Ben Shelton', meta: 'Ben Shelton vs Jakub Mensik · Tokyo', startText: 'Sep 29, 12:10 AM CDT',
      confidence: 'STRONG', payoutTier: 'standard', isUnder: false, pickLabel: 'OVER', valueLabel: 'Line', valueText: '11.5', unit: 'aces',
      projectionText: '13.4', hitPct: 66, breakEvenPct: 57.7, breakEvenLabel: 'Break-even 57.7% · standard', evText: '+14.4%', evTone: 'positive',
      opponentText: 'Opp allows 0.6', trust: 'Ready', source: 'PrizePicks', sampleText: 'n=34',
    })
  })

  it('marks an under so the page keeps side coloring', () => {
    const card = propCard(row({ recommendation: 'UNDER', evPct: -3.25 }))
    expect(card.isUnder).toBe(true)
    expect(card.pickLabel).toBe('UNDER')
    expect(card.evText).toBe('-3.3%')
    expect(card.evTone).toBe('negative')
  })

  it('colors EV by its sign, not the side', () => {
    const card = propCard(row({ recommendation: 'OVER', evPct: -41 }))
    expect(card.isUnder).toBe(false)
    expect(card.evTone).toBe('negative')
    expect(propCard(row({ recommendation: 'UNDER', evPct: 5 })).evTone).toBe('positive')
    expect(propCard(row({ evPct: 0 })).evTone).toBeNull()
  })

  it('carries the demon and goblin payout tiers, and none for priced books', () => {
    expect(propCard(row({ oddsType: 'demon' })).payoutTier).toBe('demon')
    expect(propCard(row({ oddsType: 'goblin' })).breakEvenLabel).toBe('Break-even 57.7% · goblin')
    const dk = propCard(row({ source: 'draftkings' }))
    expect(dk.payoutTier).toBeNull()
    expect(dk.breakEvenLabel).toBe('Break-even 57.7%')
  })

  it('shows a moneyline row as signed odds against the market probability', () => {
    const card = propCard(boardRow(moneylineBoardRows([prediction])[0]))
    expect(card).toMatchObject({
      pickLabel: 'BET', isUnder: false, valueLabel: 'Odds', valueText: '+129', unit: null, projectionText: '57.8%',
      hitPct: 57.8, source: 'Market odds', sampleText: '--', flags: ['small_sample'],
    })
    expect(card.breakEvenLabel).toMatch(/^Market \d+\.\d%$/)
    expect(card.evText).toBe('+32.4%')
  })

  it('shows a win-a-set row as the confidence, unpriced, with no bar', () => {
    const picks: MatchBestPicks = {
      matchId: 30, startUtc: null, p1Name: 'A', p2Name: 'B', tour: 'WTA', surface: 'Hard', tournament: null, round: null,
      p1WinProb: null, p2WinProb: null, p1OddsAmerican: null, p2OddsAmerican: null, h2hP1Wins: 0, h2hP2Wins: 0,
      picks: [{ pickType: 'derived', label: 'Win a Set', pick: 'A to win a set', playerName: 'A', edgePct: 0, confidence: 'LEAN', reasoning: 'Close match', modelProb: 0.74, oddsSource: 'unpriced', dataQualityFlags: [] }],
    }
    const card = propCard(boardRow(winASetBoardRows([picks])[0]))
    expect(card).toMatchObject({
      pickLabel: 'LOCK', valueLabel: 'Market', valueText: 'Unpriced', projectionText: '74.0%', hitPct: 74,
      breakEvenPct: null, breakEvenLabel: null, evText: '--', startText: 'Time unavailable',
    })
    expect(propCard(boardRow({ ...winASetBoardRows([picks])[0], confidence: null })).pickLabel).toBe('MODEL')
  })

  it('leaves out the bar when hit probability or break-even is missing', () => {
    expect(propCard(row({ hitProbability: null })).hitPct).toBeNull()
    const card = propCard(row({ breakEvenPct: null }))
    expect(card.breakEvenPct).toBeNull()
    expect(card.breakEvenLabel).toBeNull()
  })

  it('clamps hit and break-even percentages to 0-100', () => {
    const card = propCard(row({ hitProbability: 1.2, breakEvenPct: -4 }))
    expect(card.hitPct).toBe(100)
    expect(card.breakEvenPct).toBe(0)
  })

  it('passes quality flags through and falls back when fields are missing', () => {
    const card = propCard(row({ dataQualityFlags: ['small_sample', 'ungraded_stat'], playerName: null, matchup: null, tournament: null, line: null, statAvg: null, evPct: null, opponentStatAvg: null, matchesCount: null }))
    expect(card).toMatchObject({
      flags: ['small_sample', 'ungraded_stat'], playerName: 'Unknown player', meta: 'ATP · Hard', valueText: '--',
      projectionText: '--', evText: '--', evTone: null, opponentText: null, sampleText: '--',
    })
  })
})

describe('startLabel', () => {
  it('formats in Central time and says when the start is unknown', () => {
    expect(startLabel('2026-09-28T15:00:00Z')).toBe('Sep 28, 10:00 AM CDT')
    expect(startLabel(null)).toBe('Time unavailable')
  })
})

function played(matchDate: string, overrides: Partial<RecentMatchResult> = {}): RecentMatchResult {
  return { matchDate, opponentName: `Opp ${matchDate}`, score: '6-4 6-4', result: 'W', aces: 8, doubleFaults: 2, breakChancesCreated: 6, breakPointsConverted: 3, ...overrides }
}

describe('recentStatBars', () => {
  const matches = [
    played('2026-09-25', { aces: 12, doubleFaults: 4, breakPointsConverted: 2 }),
    played('2026-09-20', { aces: 5, doubleFaults: 1, breakPointsConverted: 5 }),
    played('2026-09-27', { aces: null, doubleFaults: 3, breakPointsConverted: null }),
  ]

  it('reads aces oldest first and compares each to the line', () => {
    expect(recentStatBars(matches, 'aces', 7.5)).toEqual([
      { matchDate: '2026-09-20', opponentName: 'Opp 2026-09-20', value: 5, vsLine: 'below' },
      { matchDate: '2026-09-25', opponentName: 'Opp 2026-09-25', value: 12, vsLine: 'above' },
      { matchDate: '2026-09-27', opponentName: 'Opp 2026-09-27', value: null, vsLine: null },
    ])
  })

  it('reads double faults and every break-points market key', () => {
    expect(recentStatBars(matches, 'double_faults', 2.5)?.map(bar => bar.value)).toEqual([1, 4, 3])
    for (const key of ['break_points', 'break_points_converted', 'Break Points Won']) {
      expect(recentStatBars(matches, key, 2.5)?.map(bar => bar.vsLine)).toEqual(['above', 'below', null])
    }
  })

  it('marks a value equal to the line as a push', () => {
    expect(recentStatBars([played('2026-09-01', { aces: 7 })], 'aces', 7)?.[0].vsLine).toBe('push')
  })

  it('returns null for markets neither the score nor a box score can settle', () => {
    expect(recentStatBars(matches, 'winners', 21.5)).toBeNull()
    expect(recentStatBars(matches, 'unforced_errors', 9.5)).toBeNull()
  })

  it('reads score-derived markets from the player-oriented score, a 7-6 set as 13 games', () => {
    const scored = [played('2026-09-01', { score: '4-6 7-6(5) 7-5', result: 'W' })]
    const value = (stat: string) => recentStatBars(scored, stat, 0)?.[0].value
    expect(value('total_games')).toBe(35)
    expect(value('total_games_won')).toBe(18)
    expect(value('total_sets')).toBe(3)
    expect(value('total_tie_breaks')).toBe(1)
    expect(value('1st_set_total_games')).toBe(10)
    expect(value('1st_set_total_games_won')).toBe(4)
  })

  it('gives no score-derived value for a retirement or a missing score', () => {
    expect(recentStatBars([played('2026-09-01', { score: '6-3 2-1 RET' })], 'total_games', 20.5)?.[0].value).toBeNull()
    expect(recentStatBars([played('2026-09-01', { score: '3-6 3-5', result: 'W' })], 'total_games', 20.5)?.[0].value).toBeNull()
    expect(recentStatBars([played('2026-09-01', { score: '6-4 3-6', result: 'W' })], 'total_sets', 2.5)?.[0].value).toBeNull()
    expect(recentStatBars([played('2026-09-01', { score: null })], 'total_sets', 2.5)?.[0].value).toBeNull()
  })

  it('does not reorder the input list', () => {
    recentStatBars(matches, 'aces', 7.5)
    expect(matches.map(match => match.matchDate)).toEqual(['2026-09-25', '2026-09-20', '2026-09-27'])
  })
})

describe('fantasyScore', () => {
  it('scores games, sets, aces and double faults the PrizePicks way', () => {
    // 10 + (12 - 7) + 3 * (2 - 0) + 0.5 * 8 - 0.5 * 2
    expect(fantasyScore(played('2026-09-01', { score: '6-4 6-3', aces: 8, doubleFaults: 2 }))).toBe(24)
    // 10 + (17 - 18) + 3 * (1 - 2) + 0.5 * 4 - 0.5 * 3
    expect(fantasyScore(played('2026-09-01', { score: '6-4 5-7 6-7(3)', result: 'L', aces: 4, doubleFaults: 3 }))).toBe(6.5)
  })

  it('needs the score and both box-score counts', () => {
    expect(fantasyScore(played('2026-09-01', { aces: null }))).toBeNull()
    expect(fantasyScore(played('2026-09-01', { doubleFaults: null }))).toBeNull()
    expect(fantasyScore(played('2026-09-01', { score: '6-4 1-0 RET' }))).toBeNull()
  })
})
