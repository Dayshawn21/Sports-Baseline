import { describe, expect, it } from 'vitest'
import type { BestPick, MatchBestPicks, MatchDetail, PropLine } from '~/types/tennis'
import { canLoadMatchPicks, matchPickGroups, matchPropCategories } from '~/utils/tennisMatchBoard'
import { buildTennisPropBoard } from '~/utils/tennisPropBoard'

const detail: MatchDetail = {
  matchId: 5, status: 'scheduled', startUtc: '2026-10-22T18:45:00Z', tour: 'ATP', tourLabel: 'ATP',
  surface: 'Hard', indoor: true, tournament: 'Lyon', round: 'R16', bestOf: 3, score: null, winnerSide: null,
  p1: { playerId: 1, name: 'Player One', rank: null, hand: null, country: null, elo: null, eloSurface: null },
  p2: { playerId: 2, name: 'Player Two', rank: null, hand: null, country: null, elo: null, eloSurface: null },
  h2h: { p1Wins: 0, p2Wins: 0, surfaceP1Wins: null, surfaceP2Wins: null }, meetings: [],
  prediction: null, predictionSource: null, predictionGeneratedAt: null, modelVersion: null, mlPick: null,
}

function prop(id: number, overrides: Partial<PropLine> = {}): PropLine {
  return { id, playerId: 1, playerName: 'Player One', matchId: 5, source: 'prizepicks', statType: 'aces',
    line: '5.5', oddsType: 'standard', fetchedAt: '2026-10-22T15:00:00Z', startTime: detail.startUtc,
    pOver: null, pUnder: null, confidence: 'PASS', ...overrides }
}

const pick: BestPick = { pickType: 'derived', label: 'Game Spread', pick: 'Player One -2.5',
  playerName: 'Player One', edgePct: 12, confidence: 'STRONG', reasoning: 'Test', evPct: 12,
  oddsAmerican: -110, kellyFraction: .03 }

function bestMatch(matchId = 5, picks = [pick]): MatchBestPicks {
  return { matchId, startUtc: detail.startUtc, p1Name: 'Player One', p2Name: 'Player Two', tour: 'ATP',
    surface: 'Hard', tournament: 'Lyon', round: 'R16', p1WinProb: .6, p2WinProb: .4,
    p1OddsAmerican: -110, p2OddsAmerican: 100, h2hP1Wins: 0, h2hP2Wins: 0, picks }
}

const ids = (props: PropLine[], player: number | null = null) =>
  matchPropCategories(props, detail, 'prizepicks', player).flatMap(c => [...c.rateable, ...c.other]).map(p => p.id)

describe('match prop scoping', () => {
  it('never includes another match or an unlinked line, even with the same player name', () => {
    expect(ids([prop(1), prop(2, { matchId: 6 }), prop(3, { matchId: null })])).toEqual([1])
  })
  it('keeps PASS, line-only, and alternate lines, with goblins as references', () => {
    const lines = [prop(1), prop(2, { confidence: null }), prop(3, { oddsType: 'goblin' })]
    expect(ids(lines)).toEqual([1, 2, 3])
    expect(buildTennisPropBoard(lines, [], 'prizepicks')[0].other.map(p => p.id)).toEqual([1, 2])
  })
  it('filters players by ID, falls back to a name only if ID is absent, and rejects unknown IDs', () => {
    const lines = [prop(1), prop(2, { playerId: 2, playerName: 'Player Two' }),
      prop(3, { playerId: null, playerName: ' player one ' }), prop(4, { playerId: 99 })]
    expect(ids(lines, 1).sort()).toEqual([1, 3])
    expect(ids(lines, 2)).toEqual([2])
    expect(ids(lines, 99)).toEqual([])
  })
  it('isolates sources and markets without losing the match constraint', () => {
    const categories = matchPropCategories([prop(1), prop(2, { source: 'dk' }),
      prop(3, { statType: 'double_faults' }), prop(4, { matchId: 6 })], detail, 'prizepicks', 1)
    expect(categories.find(c => c.market === 'aces')?.other.map(p => p.id)).toEqual([1])
    expect(categories.find(c => c.market === 'double_faults')?.other.map(p => p.id)).toEqual([3])
  })
})

describe('match picks', () => {
  it('uses only this match and the existing best-bet/angle rules', () => {
    const groups = matchPickGroups(detail, [bestMatch(9), bestMatch(5, [pick,
      { ...pick, pick: 'Unpriced angle', evPct: null, oddsAmerican: null },
      { ...pick, pick: 'Pass', confidence: 'PASS' }, { ...pick, pick: 'Negative EV', evPct: -5 },
      { ...pick, pickType: 'prop', pick: 'Already in prop table' }])])
    expect(groups.bestBets.map(p => p.pick)).toEqual([pick.pick])
    expect(groups.angles.map(p => p.pick)).toEqual(['Unpriced angle'])
  })
  it.each(['completed', 'cancelled', 'walkover'])('does not request or show current picks for %s matches', status => {
    const finished = { ...detail, status }
    expect(canLoadMatchPicks(finished)).toBe(false)
    expect(matchPickGroups(finished, [bestMatch()])).toEqual({ bestBets: [], angles: [] })
  })
  it('does not fetch a whole undated slate for a match with no start time', () => {
    expect(canLoadMatchPicks({ ...detail, startUtc: null })).toBe(false)
  })
})
