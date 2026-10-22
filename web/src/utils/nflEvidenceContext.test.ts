import { describe, expect, it } from 'vitest'
import type { NflAllowedMetric, NflGameContext, NflUsageWindow } from '~/types/nfl'
import { evidenceAllowedMeasures, evidenceContextGameId, evidenceUsageMeasures, selectedEvidenceContext } from './nflEvidenceContext'

const METRIC: NflAllowedMetric = { value: 0, observedGames: 1, eligibleGames: 2, windowStart: '2026-10-18', windowEnd: '2026-10-18', reason: null, rank: 1, rankedTeams: 28 }
const WINDOW: NflUsageWindow = { targets: METRIC, carries: METRIC, targetShare: METRIC, carryShare: METRIC, avgGameSnapShare: METRIC, teams: ['OLD', 'A'] }
const ALLOWED = { rbCarries: METRIC, rbRushYards: METRIC, rbReceptions: METRIC, rbRecYards: METRIC, wrReceptions: METRIC, wrRecYards: METRIC, teReceptions: METRIC, teRecYards: METRIC }
const ROW = { lineId: 10, playerId: 1, position: 'WR', market: 'receiving_yards', opponentTeam: 'WRONG' }
const GAME = { gameId: 94, awayTeam: 'A', homeTeam: 'B', lines: [ROW] }
const CONTEXT: NflGameContext = {
  gameId: 94, season: 2026, week: 7, cutoffWeek: 6,
  matchupContext: { away: { teamId: 1, team: 'A', allowed: ALLOWED }, home: { teamId: 2, team: 'B', allowed: ALLOWED } },
  players: [{ playerId: 1, name: 'Player', position: 'WR', team: 'A', seasonUsage: WINDOW, recentUsage: WINDOW }],
}

describe('relevant opponent measures', () => {
  for (const position of ['RB', 'WR', 'TE']) {
    it.each(['receptions', 'receiving_yards', 'receiving_targets'])(`${position} %s uses receptions and rec yards only`, market => {
      expect(evidenceAllowedMeasures(position, market).map(row => row.key)).toEqual([`${position.toLowerCase()}Receptions`, `${position.toLowerCase()}RecYards`])
    })
  }
  it.each(['rushing_yards', 'rushing_attempts'])('RB %s uses the rushing measures', market => {
    expect(evidenceAllowedMeasures('RB', market).map(row => row.key)).toEqual(['rbCarries', 'rbRushYards'])
  })
  it.each([
    ['QB', 'passing_yards'], ['QB', 'rushing_yards'], ['WR', 'rushing_yards'], ['TE', 'rushing_attempts'],
    ['RB', 'fantasy_points'], ['WR', 'anytime_touchdown'], ['RB', 'rushing_receiving_yards'], ['K', 'receptions'], [null, 'receiving_targets'],
  ])('omits unsupported %s / %s matchup measures', (position, market) => {
    expect(evidenceAllowedMeasures(position, market)).toEqual([])
  })
})

describe('neutral usage measures', () => {
  it('omits receiving usage for QB but retains carries, carry share and snap mean', () => {
    expect(evidenceUsageMeasures('QB').map(row => row.key)).toEqual(['carries', 'carryShare', 'avgGameSnapShare'])
  })
  it.each(['RB', 'WR', 'TE'])('keeps all meaningful measures for %s', position => {
    expect(evidenceUsageMeasures(position).map(row => row.key)).toEqual(['targets', 'targetShare', 'carries', 'carryShare', 'avgGameSnapShare'])
  })
  it.each(['K', 'FB', '', null])('has no invented usage for %s', position => {
    expect(evidenceUsageMeasures(position)).toEqual([])
  })
})

describe('selected identity and disabled query guards', () => {
  it('enables only a matching line in a valid selected game', () => {
    expect(evidenceContextGameId(GAME, ROW)).toBe(94)
    expect(evidenceContextGameId(null, ROW)).toBeNull()
    expect(evidenceContextGameId({ ...GAME, gameId: 0 }, ROW)).toBeNull()
    expect(evidenceContextGameId({ ...GAME, gameId: NaN }, ROW)).toBeNull()
    expect(evidenceContextGameId({ ...GAME, gameId: 1.5 }, ROW)).toBeNull()
    expect(evidenceContextGameId(GAME, { ...ROW, lineId: 20 })).toBeNull()
    expect(evidenceContextGameId(GAME, { ...ROW, playerId: 2 })).toBeNull()
    expect(evidenceContextGameId(GAME, { ...ROW, market: 'receptions' })).toBeNull()
    expect(evidenceContextGameId(GAME, { ...ROW, position: 'K' })).toBeNull()
  })
  it('uses current-week roster identity and preserves raw zero and coverage', () => {
    const result = selectedEvidenceContext(CONTEXT, GAME, ROW)
    expect(result?.opponent.team).toBe('B')
    expect(result?.player.seasonUsage.targetShare).toBe(METRIC)
    expect(result?.player.seasonUsage.teams).toEqual(['OLD', 'A'])
    const atHome = { ...CONTEXT, players: [{ ...CONTEXT.players[0], team: 'B' }] }
    expect(selectedEvidenceContext(atHome, GAME, ROW)?.opponent.team).toBe('A')
  })
  it('cannot retain another game, player, roster position or ambiguous membership', () => {
    expect(selectedEvidenceContext(undefined, GAME, ROW)).toBeNull()
    expect(selectedEvidenceContext(CONTEXT, null, ROW)).toBeNull()
    expect(selectedEvidenceContext({ ...CONTEXT, gameId: 95 }, GAME, ROW)).toBeNull()
    expect(selectedEvidenceContext(CONTEXT, GAME, { ...ROW, playerId: 2 })).toBeNull()
    expect(selectedEvidenceContext({ ...CONTEXT, players: [] }, GAME, ROW)).toBeNull()
    expect(selectedEvidenceContext({ ...CONTEXT, players: [CONTEXT.players[0], CONTEXT.players[0]] }, GAME, ROW)).toBeNull()
    expect(selectedEvidenceContext({ ...CONTEXT, players: [{ ...CONTEXT.players[0], position: 'QB' }] }, GAME, ROW)).toBeNull()
    expect(selectedEvidenceContext({ ...CONTEXT, players: [{ ...CONTEXT.players[0], team: 'C' }] }, GAME, ROW)).toBeNull()
    expect(selectedEvidenceContext({ ...CONTEXT, matchupContext: { ...CONTEXT.matchupContext, away: { ...CONTEXT.matchupContext.away, team: 'C' } } }, GAME, ROW)).toBeNull()
  })
})
