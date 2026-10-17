import { describe, expect, it } from 'vitest'
import type { BestPick, MatchDetail, MatchPrediction, PropLine } from '~/types/tennis'
import { componentRows, fmtBreakPoints, fmtMatchDate, fmtMatchDateYear, heroSide, isFinished, matchProps, meetingsNote, matchContext, parseMatchId, playerBadge, playerMeta, sideView, weightColumnLabel } from '~/utils/tennisMatch'

const prediction: MatchPrediction = {
  matchId: 5, startUtc: null, p1Name: 'Jakub Mensik', p2Name: 'Ben Shelton', tour: 'ATP', tourLabel: 'ATP',
  surface: 'Hard', tournament: 'Tokyo', round: 'R16', p1WinProb: 0.524, p2WinProb: 0.476,
  p1EloProb: 0.463, p1MlProb: 0.618, p1MarketProb: 0.456, ensembleWeights: {}, qualityFlags: [],
  p1OddsAmerican: 122, p2OddsAmerican: -148, h2hP1Wins: 1, h2hP2Wins: 2,
}

function pick(playerName: string | null): BestPick {
  return { pickType: 'moneyline', label: 'Moneyline', pick: 'x', playerName, edgePct: 14.9, confidence: 'STRONG', reasoning: '' }
}

function detail(overrides: Partial<MatchDetail> = {}): MatchDetail {
  return {
    matchId: 5, status: 'scheduled', startUtc: null, tour: 'ATP', tourLabel: 'ATP', surface: 'Hard',
    indoor: true, tournament: 'Tokyo', round: 'R16', bestOf: 3, score: null, winnerSide: null,
    p1: { playerId: 1, name: 'Jakub Mensik', rank: 19, hand: 'R', country: 'CZE', elo: 1942, eloSurface: 1968.4 },
    p2: { playerId: 2, name: 'Ben Shelton', rank: 7, hand: 'L', country: 'USA', elo: 1980, eloSurface: 1994 },
    h2h: { p1Wins: 1, p2Wins: 2, surfaceP1Wins: 1, surfaceP2Wins: 1 },
    meetings: [],
    prediction, predictionSource: 'live', predictionGeneratedAt: null, modelVersion: null, mlPick: null,
    ...overrides,
  }
}

describe('parseMatchId', () => {
  it('accepts a positive whole number only', () => {
    expect(parseMatchId('82864')).toBe(82864)
    expect(parseMatchId(undefined)).toBeNull()
    expect(parseMatchId('0')).toBeNull()
    expect(parseMatchId('-4')).toBeNull()
    expect(parseMatchId('12abc')).toBeNull()
    expect(parseMatchId('1.5')).toBeNull()
    expect(parseMatchId('99999999999999999999')).toBeNull()
  })
})

describe('heroSide', () => {
  it('leads with the moneyline play', () => {
    expect(heroSide(detail({ mlPick: pick('Ben Shelton') }))).toBe('p2')
    expect(heroSide(detail({ mlPick: pick('Jakub Mensik') }))).toBe('p1')
  })

  it('falls back to the model favorite', () => {
    expect(heroSide(detail())).toBe('p1')
    expect(heroSide(detail({ prediction: { ...prediction, p1WinProb: 0.4, p2WinProb: 0.6 } }))).toBe('p2')
  })

  it('defaults to p1 without a prediction', () => {
    expect(heroSide(detail({ prediction: null }))).toBe('p1')
  })
})

describe('sideView', () => {
  it('reads p1 directly and flips the market for p2', () => {
    expect(sideView(detail(), 'p1')).toEqual({ side: 'p1', name: 'Jakub Mensik', modelProb: 0.524, marketProb: 0.456, odds: 122 })
    const p2 = sideView(detail(), 'p2')
    expect(p2.marketProb).toBeCloseTo(0.544, 10)
    expect([p2.modelProb, p2.odds]).toEqual([0.476, -148])
  })

  it('leaves unknowns null rather than 0', () => {
    const view = sideView(detail({ prediction: { ...prediction, p1MarketProb: null, p2OddsAmerican: null } }), 'p2')
    expect([view.marketProb, view.odds]).toEqual([null, null])
    expect(sideView(detail({ prediction: null }), 'p1').modelProb).toBeNull()
  })
})

describe('matchContext', () => {
  it('joins the known parts', () => {
    expect(matchContext(detail())).toBe('Tokyo · R16 · Hard, indoor · Bo3')
    expect(matchContext(detail({ indoor: false, round: null, bestOf: 5 }))).toBe('Tokyo · Hard · Bo5')
    expect(matchContext(detail({ surface: null, tournament: null }))).toBe('R16 · Bo3')
  })
})

describe('playerMeta', () => {
  it('prefers the surface ELO and drops unknown parts', () => {
    expect(playerMeta(detail().p1, 'Hard')).toBe('#19 · R · ELO hard 1968')
    expect(playerMeta({ ...detail().p1, eloSurface: null }, 'Hard')).toBe('#19 · R · ELO 1942')
    expect(playerMeta({ ...detail().p1, rank: null, hand: null, elo: null, eloSurface: null }, null)).toBe('')
  })
})

describe('playerBadge', () => {
  it('uses the country, else initials', () => {
    expect(playerBadge(detail().p1)).toBe('CZE')
    expect(playerBadge({ ...detail().p1, country: null })).toBe('JM')
  })
})

describe('isFinished', () => {
  it('treats anything but scheduled or live as finished', () => {
    expect(isFinished(detail())).toBe(false)
    expect(isFinished(detail({ status: 'live' }))).toBe(false)
    expect(isFinished(detail({ status: 'completed' }))).toBe(true)
    expect(isFinished(detail({ status: 'walkover' }))).toBe(true)
  })
})

describe('matchProps', () => {
  function prop(id: number, matchId: number | null, oddsType: string | null, confidence: string | null): PropLine {
    return {
      id, matchId, oddsType, confidence, playerId: null, source: 'prizepicks', statType: 'aces',
      line: '10.5', fetchedAt: '2026-09-28T00:00:00Z', startTime: null, pOver: null, pUnder: null,
    }
  }

  it('keeps this match only, standard before goblin and demon, then by tier', () => {
    const props = [
      prop(1, 5, 'demon', null),
      prop(2, 5, 'standard', 'LEAN'),
      prop(3, 9, 'standard', 'LOCK'),
      prop(4, 5, 'goblin', 'STRONG'),
      prop(5, 5, 'standard', 'STRONG'),
      prop(6, 5, null, null),
    ]

    expect(matchProps(props, 5).map((p) => p.id)).toEqual([5, 2, 6, 4, 1])
  })

  it('is empty for a match with no lines', () => {
    expect(matchProps([prop(1, 9, 'standard', 'LOCK')], 5)).toEqual([])
  })
})

describe('fmtMatchDateYear', () => {
  it('includes the year and keeps the calendar day', () => {
    expect(fmtMatchDateYear('2026-02-18')).toBe('Feb 18, 2026')
    expect(fmtMatchDateYear('2023-01-01')).toBe('Jan 1, 2023')
    expect(fmtMatchDateYear('soon')).toBe('soon')
  })
})

describe('meetingsNote', () => {
  it('says how many counted meetings are listed when some are missing', () => {
    expect(meetingsNote(3, 5)).toBe('3 of 5 meetings shown · stored since 2023')
    expect(meetingsNote(0, 2)).toBe('0 of 2 meetings shown · stored since 2023')
  })

  it('is silent when every counted meeting is listed, or more are', () => {
    expect(meetingsNote(1, 1)).toBeNull()
    expect(meetingsNote(2, 1)).toBeNull()
    expect(meetingsNote(0, 0)).toBeNull()
  })
})

describe('fmtBreakPoints', () => {
  it('shows won out of created, or a dash', () => {
    expect(fmtBreakPoints(2, 5)).toBe('2/5')
    expect(fmtBreakPoints(0, 3)).toBe('0/3')
    expect(fmtBreakPoints(0, 0)).toBe('—')
    expect(fmtBreakPoints(null, 4)).toBe('—')
    expect(fmtBreakPoints(1, null)).toBe('—')
  })
})

describe('fmtMatchDate', () => {
  it('keeps the calendar day whatever the local zone', () => {
    expect(fmtMatchDate('2026-09-25')).toBe('Sep 25')
    expect(fmtMatchDate('2026-01-01')).toBe('Jan 1')
  })

  it('passes through anything it cannot parse', () => {
    expect(fmtMatchDate('soon')).toBe('soon')
  })
})

describe('componentRows', () => {
  it('reads every component for the given side with its weight', () => {
    const rows = componentRows(detail({ prediction: { ...prediction, ensembleWeights: { elo: 0.35, ml: 0.4, market: 0.25 } } }), 'p1')

    expect(rows.map((r) => [r.key, r.label, r.prob, r.weight, r.missingNote])).toEqual([
      ['elo', 'ELO (hard)', 0.463, 0.35, null],
      ['ml', 'LightGBM', 0.618, 0.4, null],
      ['market', 'Market', 0.456, 0.25, null],
      ['ensemble', 'Ensemble', 0.524, null, null],
    ])
  })

  it('flips every probability for p2', () => {
    const rows = componentRows(detail(), 'p2')

    expect(rows[0].prob).toBeCloseTo(0.537, 10)
    expect(rows[2].prob).toBeCloseTo(0.544, 10)
    expect(rows[3].prob).toBe(0.476)
  })

  it('says why the ML row is empty on a tour it was not trained for', () => {
    const rows = componentRows(detail({
      prediction: { ...prediction, p1MlProb: null, ensembleWeights: { elo: 0.8, market: 0.2 }, qualityFlags: ['ml_missing', 'ml_not_trained_for_tour'] },
    }), 'p1')

    expect(rows[1]).toMatchObject({ prob: null, weight: null, missingNote: 'not trained for this tour' })
  })

  it('marks any other missing component as no data, never 0%', () => {
    const rows = componentRows(detail({ surface: null, prediction: { ...prediction, p1EloProb: null, p1MarketProb: null } }), 'p1')

    expect(rows[0]).toMatchObject({ label: 'ELO', prob: null, missingNote: 'no data' })
    expect(rows[2]).toMatchObject({ prob: null, missingNote: 'no data' })
  })
})

describe('weightColumnLabel', () => {
  it('reads Coef for a stored ensemble-v3 prediction', () => {
    expect(weightColumnLabel(detail({ predictionSource: 'stored', modelVersion: 'ensemble-v3+lgbm-v6' }))).toBe('Coef')
  })

  it('reads Weight for a stored v1 or v2 prediction', () => {
    expect(weightColumnLabel(detail({ predictionSource: 'stored', modelVersion: 'ensemble-v2+lgbm-v6' }))).toBe('Weight')
    expect(weightColumnLabel(detail({ predictionSource: 'stored', modelVersion: 'ensemble-v1+lgbm-v5' }))).toBe('Weight')
  })

  it('reads Coef for a live prediction with a market price, which is always v3', () => {
    expect(weightColumnLabel(detail({ predictionSource: 'live', modelVersion: null }))).toBe('Coef')
  })

  it('reads Weight for a live prediction without a market price, which takes the hand-set blend', () => {
    expect(weightColumnLabel(detail({ prediction: { ...prediction, p1MarketProb: null } }))).toBe('Weight')
  })
})
