import { describe, expect, it } from 'vitest'
import type { BestPick, MatchPrediction, PropLine } from '~/types/tennis'
import type { UnifiedTennisMatch } from '~/utils/unifiedTennis'
import { OTHER_TOURNAMENT, featuredPicks, filterByTourTab, fmtEv, isGroupedSort, tableGroups, groupByTournament, slateRow, slateRows, tourTone } from '~/utils/tennisSlate'

function prediction(over: Partial<MatchPrediction> = {}): MatchPrediction {
  return {
    matchId: 1,
    startUtc: '2026-09-28T10:30:00Z',
    p1Name: 'Jakub Mensik',
    p2Name: 'Ben Shelton',
    tour: 'ATP',
    surface: 'Hard',
    tournament: 'Tokyo',
    round: 'R16',
    p1WinProb: 0.524,
    p2WinProb: 0.476,
    p1EloProb: 0.498,
    p1MlProb: 0.541,
    p1MarketProb: 0.456,
    ensembleWeights: {},
    qualityFlags: [],
    p1OddsAmerican: 128,
    p2OddsAmerican: -150,
    h2hP1Wins: 1,
    h2hP2Wins: 0,
    ...over,
  }
}

// Clears isPricedBestBet for STRONG: EV >= 10, Kelly >= 0.02, priced.
function bestBet(over: Partial<BestPick> = {}): BestPick {
  return {
    pickType: 'moneyline',
    label: 'Moneyline',
    pick: 'Mensik ML (+128)',
    playerName: 'Jakub Mensik',
    edgePct: 6.8,
    confidence: 'STRONG',
    reasoning: 'model over market',
    oddsAmerican: 128,
    evPct: 14.2,
    kellyFraction: 0.04,
    ...over,
  }
}

// Unpriced, so it is an angle, never a best bet.
function angle(over: Partial<BestPick> = {}): BestPick {
  return bestBet({ pickType: 'derived', pick: 'Set score 2-0', oddsAmerican: null, evPct: null, kellyFraction: null, ...over })
}

function prop(over: Partial<PropLine> = {}): PropLine {
  return {
    id: 1,
    playerId: 10,
    playerName: 'Jakub Mensik',
    matchId: null,
    source: 'prizepicks',
    statType: 'aces',
    line: '9.5',
    oddsType: 'standard',
    fetchedAt: '2026-09-28T08:00:00Z',
    startTime: '2026-09-28T10:30:00Z',
    pOver: 0.62,
    pUnder: 0.38,
    confidence: 'STRONG',
    ...over,
  }
}

function match(over: Partial<UnifiedTennisMatch> = {}): UnifiedTennisMatch {
  return {
    key: 'm1',
    matchId: 1,
    prediction: prediction(),
    bestMatch: null,
    bestPicks: [],
    props: [],
    inferredPropLink: false,
    ...over,
  }
}

describe('slateRow', () => {
  it('carries both players, each probability pair, the odds, and a best bet', () => {
    const row = slateRow(match({ bestPicks: [bestBet()] }))
    expect(row.players).toEqual(['Jakub Mensik', 'Ben Shelton'])
    expect(row.model).toEqual([0.524, 0.476])
    expect(row.market?.[0]).toBe(0.456)
    expect(row.market?.[1]).toBeCloseTo(0.544)
    expect(row.odds).toEqual([128, -150])
    expect(row.primaryPick?.pick).toBe('Mensik ML (+128)')
    expect(row.primaryIsBestBet).toBe(true)
  })

  it('falls back to an angle, marked as not a best bet, so its EV is never colored as a play', () => {
    const row = slateRow(match({ bestPicks: [angle()] }))
    expect(row.primaryPick?.pick).toBe('Set score 2-0')
    expect(row.primaryIsBestBet).toBe(false)
  })

  it('has no pick when the match has neither a best bet nor an angle', () => {
    const row = slateRow(match())
    expect(row.primaryPick).toBeNull()
    expect(row.primaryIsBestBet).toBe(false)
  })

  it('keeps the highest-EV prop as the fallback when the match has no pick', () => {
    const row = slateRow(match({ props: [prop({ id: 1, evPct: 4 }), prop({ id: 2, statType: 'total_games', evPct: 16.7 }), prop({ id: 3, evPct: null })] }))
    expect(row.primaryPick).toBeNull()
    expect(row.primaryProp?.id).toBe(2)
  })

  it('leaves a probability pair null when the prediction lacks it, instead of inventing a 50/50', () => {
    const row = slateRow(match({ prediction: prediction({ p1MlProb: null, p1EloProb: null }) }))
    expect(row.ml).toBeNull()
    expect(row.elo).toBeNull()
    expect(row.model).not.toBeNull()
  })

  it('builds a prop-only row from the prop players, with no probabilities or tournament', () => {
    const row = slateRow(match({
      key: 'props:mensik',
      matchId: null,
      prediction: null,
      props: [prop(), prop({ id: 2, statType: 'double_faults' })],
    }))
    expect(row.players).toEqual(['Jakub Mensik', null])
    expect(row.model).toBeNull()
    expect(row.tournament).toBeNull()
    expect(row.startUtc).toBe('2026-09-28T10:30:00Z')
    expect(row.propCount).toBe(2)
  })

  it('shows the same quality flags the workspace does', () => {
    const row = slateRow(match({ prediction: prediction({ qualityFlags: ['market_stale'] }) }))
    expect(row.flags).toEqual(['market_stale'])
  })
})

describe('groupByTournament', () => {
  it('orders groups by their first row and keeps rows in the input sort order', () => {
    const rows = slateRows([
      match({ key: 'a', prediction: prediction({ tournament: 'Beijing' }) }),
      match({ key: 'b', prediction: prediction({ tournament: 'Tokyo' }) }),
      match({ key: 'c', prediction: prediction({ tournament: 'Beijing' }) }),
    ])
    const groups = groupByTournament(rows)
    expect(groups.map((group) => group.tournament)).toEqual(['Beijing', 'Tokyo'])
    expect(groups[0].rows.map((row) => row.key)).toEqual(['a', 'c'])
  })

  it('puts rows without a tournament under Other', () => {
    const groups = groupByTournament(slateRows([match({ key: 'p', prediction: null, props: [prop()] })]))
    expect(groups).toEqual([{ tournament: OTHER_TOURNAMENT, rows: [expect.objectContaining({ key: 'p' })] }])
  })
})

describe('fmtEv', () => {
  it('signs positive and negative EV to one decimal', () => {
    expect(fmtEv(61.25)).toBe('+61.3%')
    expect(fmtEv(-6.4)).toBe('-6.4%')
    expect(fmtEv(0)).toBe('+0.0%')
  })

  it('shows a dash when the pick is unpriced', () => {
    expect(fmtEv(null)).toBe('—')
    expect(fmtEv(Number.NaN)).toBe('—')
  })
})

describe('filterByTourTab', () => {
  const rows = slateRows([
    match({ key: 'atp', prediction: prediction({ tour: 'ATP' }) }),
    match({ key: 'wta', prediction: prediction({ tour: 'WTA', tourLabel: 'WTA' }) }),
    match({ key: 'ch', prediction: prediction({ tour: 'CHALLENGER', tourLabel: 'Challenger' }) }),
    match({ key: 'w125', prediction: prediction({ tour: 'CHALLENGER', tourLabel: 'WTA 125' }) }),
    match({ key: 'props', prediction: null, props: [prop()] }),
  ])
  const keys = (tab: Parameters<typeof filterByTourTab>[1]) => filterByTourTab(rows, tab).map((row) => row.key)

  it('keeps every row, prop-only ones included, on All', () => {
    expect(keys('all')).toEqual(['atp', 'wta', 'ch', 'w125', 'props'])
  })

  it('splits WTA 125 out of Challenger', () => {
    expect(keys('CHALLENGER')).toEqual(['ch'])
    expect(keys('WTA 125')).toEqual(['w125'])
  })

  it('filters the plain tours', () => {
    expect(keys('ATP')).toEqual(['atp'])
    expect(keys('WTA')).toEqual(['wta'])
  })
})

describe('tourTone', () => {
  it('colors WTA 125 as WTA even though the feed files it under CHALLENGER', () => {
    expect(tourTone('CHALLENGER', 'WTA 125')).toBe('wta')
  })

  it('maps the plain tour codes', () => {
    expect(tourTone('ATP')).toBe('atp')
    expect(tourTone('WTA', 'WTA')).toBe('wta')
    expect(tourTone('CHALLENGER', 'Challenger')).toBe('challenger')
    expect(tourTone('CHALLENGER')).toBe('challenger')
  })

  it('has no tone for an unknown or missing tour', () => {
    expect(tourTone(null)).toBeNull()
    expect(tourTone('ITF')).toBeNull()
  })
})

describe('isGroupedSort and tableGroups', () => {
  it('groups by tournament only in time order', () => {
    expect(isGroupedSort('start')).toBe(true)
    expect(isGroupedSort('start_desc')).toBe(true)
    expect(isGroupedSort('opportunity')).toBe(false)
    expect(isGroupedSort('ev')).toBe(false)
  })

  it('keeps a ranking sort as one header-less list, so the best match stays first', () => {
    const rows = slateRows([
      match({ key: 'a', prediction: prediction({ tournament: 'Beijing' }) }),
      match({ key: 'b', prediction: prediction({ tournament: 'Tokyo' }) }),
      match({ key: 'c', prediction: prediction({ tournament: 'Beijing' }) }),
    ])
    const flat = tableGroups(rows, false)
    expect(flat).toHaveLength(1)
    expect(flat[0].tournament).toBeNull()
    expect(flat[0].rows.map((row) => row.key)).toEqual(['a', 'b', 'c'])
    expect(tableGroups(rows, true).map((group) => group.tournament)).toEqual(['Beijing', 'Tokyo'])
  })

  it('returns no groups for no rows, so the table shows its empty state', () => {
    expect(tableGroups([], false)).toEqual([])
  })
})

describe('featuredPicks', () => {
  it('takes the first best bet of each match in input order, skipping matches without one', () => {
    const featured = featuredPicks([
      match({ key: 'angle-only', bestPicks: [angle()] }),
      match({ key: 'x', bestPicks: [bestBet({ pick: 'X' })] }),
      match({ key: 'empty' }),
      match({ key: 'y', bestPicks: [bestBet({ pick: 'Y' }), bestBet({ pick: 'Y2' })] }),
    ], 4)
    expect(featured.map(({ match: m, pick }) => `${m.key}:${pick.pick}`)).toEqual(['x:X', 'y:Y'])
  })

  it('stops at the limit', () => {
    const matches = ['a', 'b', 'c'].map((key) => match({ key, bestPicks: [bestBet()] }))
    expect(featuredPicks(matches, 2).map(({ match: m }) => m.key)).toEqual(['a', 'b'])
  })
})
