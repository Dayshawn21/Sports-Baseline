import { describe, expect, it } from 'vitest'
import type { AdoptedPick, MatchBestPicks, MatchPrediction, PropLine } from '~/types/tennis'
import type { TennisBoardLine } from '~/utils/tennisPropBoard'
import { buildTennisPropBoard, compareLines, enrichTennisPropLines, isTennisRateable, lineNumber, marketLabel, marketTitle, moneylineBoardRows, payoutTier, signalSummary, sourceLabel, trustLabel, winASetBoardRows, winASetStrength } from '~/utils/tennisPropBoard'

const prediction: MatchPrediction = {
  matchId: 10, startUtc: '2026-09-21T16:00:00Z', p1Name: 'Aryna Sabalenka', p2Name: 'Coco Gauff', tour: 'WTA', surface: 'Hard', tournament: 'Beijing', round: 'R32',
  p1WinProb: null, p2WinProb: null, p1EloProb: null, p1MlProb: null, p1MarketProb: null, ensembleWeights: {}, qualityFlags: [], p1OddsAmerican: null, p2OddsAmerican: null, h2hP1Wins: 0, h2hP2Wins: 0,
}

function prop(id: number, overrides: Partial<PropLine> = {}): PropLine {
  return {
    id, playerId: id, playerName: `Player ${id}`, matchId: 10, source: 'prizepicks', statType: 'aces', line: '5.5', oddsType: 'standard', fetchedAt: '2026-09-21T10:00:00Z', startTime: null,
    pOver: .62, pUnder: .38, confidence: null, recommendation: 'OVER', statAvg: 7, edgePct: 27, evPct: 12, hitProbability: .62, breakEvenPct: 55, matchesCount: 15, surface: null, dataQualityFlags: [], projectionStatus: 'ok', audit: { playerResolved: true, matchLinked: true, statsFresh: true, sampleSize: 15, opponentStatsFound: true, predictionFound: true, projectionFound: true },
    ...overrides,
  }
}

describe('isTennisRateable', () => {
  it('accepts a fully scored linked prop', () => expect(isTennisRateable(prop(1))).toBe(true))
  it.each([
    ['unlinked', { audit: { ...prop(1).audit!, matchLinked: false } }],
    ['stale', { dataQualityFlags: ['stale_stats'] }],
    ['stale odds', { dataQualityFlags: ['stale_odds'] }],
    ['thin', { dataQualityFlags: ['small_sample'] }],
    ['no P(over)', { pOver: null }],
    ['hard-blocked (no side)', { recommendation: null }],
    ['Moneyline', { statType: 'moneyline', statAvg: 70, line: '-110' }],
  ])('rejects %s lines', (_label, override) => expect(isTennisRateable(prop(1, override))).toBe(false))

  it('rates a line whatever its EV, since tennis lines are gray and unranked (48f)', () => {
    expect([null, -30, 0, 12].map(evPct => isTennisRateable(prop(1, { evPct })))).toEqual([true, true, true, true])
    expect(trustLabel(prop(1, { evPct: -30 }))).toBe('Reference')
  })
})

describe('buildTennisPropBoard', () => {
  it('explains the model, line, pick, and opponent context in plain language', () => {
    expect(signalSummary(prop(1, {
      recommendation: 'UNDER',
      statAvg: 3.5,
      line: '5.0',
      opponentStatAvg: 4.2,
    }))).toBe('Model projects 3.5 vs the 5.0 line. Opponent allows 4.2.')
  })

  it('filters sources and preserves provider rows', () => {
    const rows = [prop(1, { playerName: 'Aryna Sabalenka', evPct: 8 }), prop(2, { playerName: 'Aryna Sabalenka', source: 'draftkings', pOver: null }), prop(3, { statType: 'double_faults', evPct: 10 })]
    const all = buildTennisPropBoard(rows, [prediction], 'all')
    expect(all.map(category => category.market)).toEqual(['aces', 'double_faults'])
    expect(all[0].rateable.map(line => line.id)).toEqual([1])
    expect(all[0].other.map(line => line.id)).toEqual([2])
    expect(buildTennisPropBoard(rows, [prediction], 'prizepicks')[0].rateable.map(line => line.id)).toEqual([1])
  })

  it('filters linked rows by WTA, WTA 125, and Challenger labels', () => {
    const wta125: MatchPrediction = { ...prediction, matchId: 11, tour: 'WTA 125' }
    const challenger: MatchPrediction = { ...prediction, matchId: 12, tour: 'CHALLENGER' }
    const rows = [prop(1), prop(2, { matchId: 11 }), prop(3, { matchId: 12 })]

    expect(buildTennisPropBoard(rows, [prediction, wta125, challenger], 'all', 'wta').flatMap(category => category.rateable).map(row => row.id)).toEqual([1])
    expect(buildTennisPropBoard(rows, [prediction, wta125, challenger], 'all', 'wta_125').flatMap(category => category.rateable).map(row => row.id)).toEqual([2])
    expect(buildTennisPropBoard(rows, [prediction, wta125, challenger], 'all', 'challenger').flatMap(category => category.rateable).map(row => row.id)).toEqual([3])
  })

  it('puts unrateable lines in the separate all-lines bucket', () => {
    const board = buildTennisPropBoard([prop(1), prop(2, { dataQualityFlags: ['small_sample'] })], [prediction], 'all')
    expect(board[0].rateable.map(line => line.id)).toEqual([1])
    expect(board[0].other.map(line => line.id)).toEqual([2])
  })

  it('omits noisy PrizePicks Goblin alternate lines from the board', () => {
    const board = buildTennisPropBoard([
      prop(1, { oddsType: 'standard' }),
      prop(2, { oddsType: 'goblin' }),
    ], [prediction], 'all')

    expect(board[0].rateable.map(line => line.id)).toEqual([1])
    expect(board[0].other).toEqual([])
  })

  it('keeps start-time order whatever the EV or P(over), so nothing is ranked (48f)', () => {
    const board = buildTennisPropBoard([
      prop(1, { startTime: '2026-09-21T18:00:00Z', evPct: 45, pOver: .9, pUnder: .1 }),
      prop(2, { startTime: '2026-09-21T14:00:00Z', evPct: -20, pOver: .3, pUnder: .7 }),
      prop(3, { startTime: '2026-09-21T16:00:00Z', evPct: 11 }),
    ], [prediction], 'all')
    expect(board[0].rateable.map(line => line.id)).toEqual([2, 3, 1])
  })

  it('breaks a start-time tie by player, then stat, and puts lines with no start last', () => {
    const line = (id: number, overrides: Partial<TennisBoardLine>): TennisBoardLine => ({ ...prop(id), matchup: null, tournament: null, tour: null, ...overrides })
    const at = '2026-09-21T16:00:00Z'
    const rows = [
      line(1, { startTime: null, playerName: 'Ana' }),
      line(2, { startTime: at, playerName: 'Zoe' }),
      line(3, { startTime: at, playerName: 'Ana', statType: 'double_faults' }),
      line(4, { startTime: at, playerName: 'Ana', statType: 'aces' }),
    ]
    expect([...rows].sort(compareLines).map(row => row.id)).toEqual([4, 3, 2, 1])
  })

  it('adds linked match context for the evidence panel', () => {
    const [row] = enrichTennisPropLines([prop(1, { playerName: 'Aryna Sabalenka' })], [prediction], 'all')
    expect(row.matchup).toBe('Aryna Sabalenka vs Coco Gauff')
    expect(row.tournament).toBe('Beijing')
    expect(row.surface).toBe('Hard')
  })

  it('labels PrizePicks payout tiers and leaves priced sources unlabeled', () => {
    expect(payoutTier({ source: 'prizepicks', oddsType: 'demon' })).toBe('demon')
    expect(payoutTier({ source: 'prizepicks', oddsType: 'Goblin' })).toBe('goblin')
    expect(payoutTier({ source: 'prizepicks', oddsType: null })).toBe('standard')
    expect(payoutTier({ source: 'draftkings', oddsType: 'standard' })).toBeNull()
  })

  it('does not rate a row whose match has finished or is mislinked', () => {
    expect(isTennisRateable(prop(1, { dataQualityFlags: ['match_finished'] }))).toBe(false)
    expect(isTennisRateable(prop(1, { dataQualityFlags: ['match_link_invalid'] }))).toBe(false)
  })

  it('states the moneyline edge relative to the market, as the backend does', () => {
    const [row] = moneylineBoardRows([{ ...prediction, p1WinProb: .60, p2WinProb: .40, p1OddsAmerican: 100, p2OddsAmerican: 100 }])
    expect(row.edgePct).toBeCloseTo((0.60 - 0.50) / 0.50 * 100)
  })

  it('keeps a positive-EV moneyline as an unranked reference row, since moneyline picks are off', () => {
    const rows = moneylineBoardRows([{ ...prediction, p1WinProb: .62, p2WinProb: .38, p1OddsAmerican: -110, p2OddsAmerican: -110 }])
    expect(rows).toHaveLength(2)
    expect(rows[0]).toMatchObject({ playerName: 'Aryna Sabalenka', statType: 'moneyline', source: 'market', recommendation: null, confidence: null, evPct: null })
    expect(rows[0].statAvg).toBeCloseTo(62)
    expect(rows[0].breakEvenPct).toBeCloseTo(50)
    expect(rows.map(isTennisRateable)).toEqual([false, false])
    expect(rows.map(trustLabel)).toEqual(['Review', 'Review'])
    expect(signalSummary(rows[0])).toBe('Reference only: tennis moneyline picks are off')

    const [category] = buildTennisPropBoard(rows, [prediction], 'all')
    expect(category.rateable).toEqual([])
    expect(category.other).toHaveLength(2)
  })
})

// Synthetic: no real slice has been adopted.
function adopted(margin: number, side: AdoptedPick['side'] = 'over'): AdoptedPick {
  return { side, probability: .577 + margin, breakEven: .577, margin, rule: 'tennis-props-check-v1', projectionVersion: 'props-v3' }
}

describe('adopted lines (48g)', () => {
  const lines = () => [
    prop(1, { startTime: '2026-09-21T18:00:00Z', evPct: 45, pOver: .9, pUnder: .1 }),
    prop(2, { startTime: '2026-09-21T14:00:00Z', evPct: -20, pOver: .3, pUnder: .7 }),
    prop(3, { startTime: '2026-09-21T16:00:00Z', evPct: 11 }),
  ]

  it('leaves the 48f order untouched when nothing is adopted', () => {
    const plain = buildTennisPropBoard(lines(), [prediction], 'all')
    const withNulls = buildTennisPropBoard(lines().map(line => ({ ...line, adoptedPick: null })), [prediction], 'all')
    expect(plain[0].rateable.map(line => line.id)).toEqual([2, 3, 1])
    expect(withNulls[0].rateable.map(line => line.id)).toEqual([2, 3, 1])
  })

  it('ranks an adopted line ahead of earlier unadopted ones', () => {
    const [first, second, third] = lines()
    const board = buildTennisPropBoard([{ ...first, adoptedPick: adopted(.05) }, second, third], [prediction], 'all')
    expect(board[0].rateable.map(line => line.id)).toEqual([1, 2, 3])
  })

  it('orders adopted lines by margin over break-even', () => {
    const [first, second, third] = lines()
    const board = buildTennisPropBoard([
      { ...first, adoptedPick: adopted(.04) }, { ...second, adoptedPick: adopted(.09, 'under') }, third,
    ], [prediction], 'all')
    expect(board[0].rateable.map(line => line.id)).toEqual([2, 1, 3])
  })

  it('puts an adopted goblin on the board even with alternates hidden', () => {
    const board = buildTennisPropBoard([
      prop(1, { oddsType: 'goblin', adoptedPick: adopted(.06) }),
      prop(2, { oddsType: 'goblin' }),
    ], [prediction], 'all')
    expect(board[0].rateable.map(line => line.id)).toEqual([1])
    expect(board[0].other).toEqual([])
  })

  it('reads Pick only when adopted', () => {
    expect(trustLabel(prop(1, { adoptedPick: adopted(.05) }))).toBe('Pick')
    expect(trustLabel(prop(1))).toBe('Reference')
  })
})

describe('Win a Set model rows', () => {
  it.each([
    [.70, 'LOCK'],
    [.62, 'STRONG'],
    [.619, null],
  ] as const)('assigns %s a %s strength label', (probability, expected) => {
    expect(winASetStrength(probability)).toBe(expected)
  })

  it('keeps the existing unpriced derived pick out of EV rankings', () => {
    const match: MatchBestPicks = {
      ...prediction,
      picks: [{ pickType: 'derived', label: 'Win a Set', pick: 'Coco wins a set', playerName: 'Coco Gauff', edgePct: 40, confidence: 'STRONG', reasoning: 'Coco has a 70% chance of taking at least one set', modelProb: .70, oddsSource: 'unpriced' }],
    }
    const [row] = winASetBoardRows([match])
    expect(row).toMatchObject({ source: 'model', statType: 'win_a_set', confidence: 'LOCK', evPct: null, line: null })
    expect(isTennisRateable(row)).toBe(false)
    expect(signalSummary(row)).toContain('70% chance')
    expect(lineNumber(row)).toBeNull()
  })

  it('sorts model-only Win a Set rows by probability so Locks lead', () => {
    const picks = (modelProb: number): MatchBestPicks => ({
      ...prediction,
      picks: [{ pickType: 'derived', label: 'Win a Set', pick: 'Player wins a set', playerName: `Player ${modelProb}`, edgePct: 10, confidence: 'LEAN', reasoning: 'Model only', modelProb, oddsSource: 'unpriced' }],
    })
    const rows = [...winASetBoardRows([picks(.64)]), ...winASetBoardRows([picks(.72)])]
    expect(buildTennisPropBoard(rows, [], 'model')[0].other.map(row => row.hitProbability)).toEqual([.72, .64])
  })
})

describe('first-set props (16e)', () => {
  const firstSet = prop(1, { statType: '1st Set Total Games', line: '9.5', statAvg: 10.1, dataQualityFlags: ['ungraded_stat'] })

  it('labels both first-set stats', () => {
    expect(marketLabel('1st Set Total Games')).toBe('1st set games')
    expect(marketLabel('1st Set Total Games Won')).toBe('1st set games won')
    expect(marketTitle('total_games_won')).toBe('Total games won')
    expect(marketTitle('aces')).toBe('Aces')
  })

  it('reads Review until graded', () => {
    expect(isTennisRateable(firstSet)).toBe(false)
    expect(trustLabel(firstSet)).toBe('Review')
  })

  it('says the stat is new ahead of the projection', () => {
    expect(signalSummary(firstSet)).toBe('New stat, not yet graded. Model projects 10.1 vs the 9.5 line.')
  })
})

describe('sourceLabel', () => {
  it('names PrizePicks and DraftKings, and groups any other book under Market odds', () => {
    expect(sourceLabel('prizepicks')).toBe('PrizePicks')
    expect(sourceLabel('draftkings')).toBe('DraftKings')
    expect(sourceLabel('bet365')).toBe('Market odds')
    expect(sourceLabel('fanduel')).toBe('Market odds')
  })
})
