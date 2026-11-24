import { describe, expect, it } from 'vitest'
import type { NbaInjury, NbaPropBoardWireGame, NbaPropBoardWireResponse } from '~/types/nba'
import { nbaExpandPropBoard } from '~/utils/nbaPropBoardWire'

function injury(overrides: Partial<NbaInjury> = {}): NbaInjury {
  return {
    espnAthleteId: '10', playerId: 1, playerName: 'Amy', team: 'DET', athleteTeam: null, status: 'Out',
    detail: null, sourceUpdatedAt: null, returnDate: null, fetchedAt: '2026-11-23T15:00:00Z', ...overrides,
  }
}

const base = { position: 'G', oddsType: 'standard', fetchedAt: '2026-11-23T14:00:00Z' }
const modelled = {
  projection: 20, gamesInSample: 20, priorMinutes: 30, gap: 1.5, pOver: null, pUnder: null,
  overProbabilityVersion: null, flags: [],
}

function wireGame(overrides: Partial<NbaPropBoardWireGame> = {}): NbaPropBoardWireGame {
  return {
    gameId: 7, awayTeam: 'DET', homeTeam: 'NY', startUtc: '2026-11-24T00:00:00Z', status: 'scheduled', teamStats: null,
    injuryReport: {
      source: 'ESPN', fetchedAt: '2026-11-23T15:00:00Z', freshness: 'fresh',
      injuries: [
        injury(),
        injury({ playerId: 2, playerName: 'Zed', athleteTeam: 'NY' }),
        injury({ playerId: null, playerName: 'Unlinked' }),
        injury({ playerId: 4, playerName: 'Bea', team: 'NY', athleteTeam: 'NY' }),
      ],
    },
    lines: [
      { ...base, ...modelled, playerId: 1, playerName: 'Amy', team: 'DET', market: 'points', line: 18.5 },
      { ...base, ...modelled, playerId: 1, playerName: 'Amy', team: 'DET', market: 'assists', line: 4.5 },
      { ...base, ...modelled, playerId: 2, playerName: 'Zed', team: 'DET', market: 'points', line: 20.5 },
      { ...base, ...modelled, playerId: 3, playerName: 'Cy', team: null, market: 'points', line: 9.5 },
    ],
    lineOnlyLines: [{ ...base, playerId: 4, playerName: 'Bea', team: 'NY', market: 'double_double', line: 0.5 }],
    playerRecent: [
      { playerId: 1, games: [
        { gameDate: '2026-11-21', opponent: 'BOS', values: { points: 22, assists: null } },
        { gameDate: '2026-11-19', opponent: null, values: { points: 15, assists: 6 } },
      ] },
      { playerId: 2, games: [{ gameDate: '2026-11-21', opponent: 'BOS', values: { points: 11 } }] },
      { playerId: 4, games: [] },
    ],
    ...overrides,
  }
}

function board(game: NbaPropBoardWireGame): NbaPropBoardWireResponse {
  return { date: '2026-11-23', previousDate: null, nextDate: null, modelVersion: 'nba-reference-v1', games: [game] }
}

describe('nbaExpandPropBoard', () => {
  it('rebuilds each line recent games from its market, as the game page sends them', () => {
    const [game] = nbaExpandPropBoard(board(wireGame())).games
    expect(game.lines[0].recent).toEqual([
      { gameDate: '2026-11-21', opponent: 'BOS', value: 22 },
      { gameDate: '2026-11-19', opponent: null, value: 15 },
    ])
    expect(game.lines[1].recent.map(recent => recent.value)).toEqual([null, 6])
    expect(game.lines[3].recent).toEqual([])
    expect(game.lineOnlyLines[0].recent).toEqual([])
    expect('playerRecent' in game).toBe(false)
  })

  it('joins injuries by player and team with the API rule', () => {
    const [game] = nbaExpandPropBoard(board(wireGame())).games
    expect(game.lines[0].injury?.playerName).toBe('Amy')
    expect(game.lines[2].injury).toBeNull()
    expect(game.lines[3].injury).toBeNull()
    expect(game.lineOnlyLines[0].injury?.playerName).toBe('Bea')
  })

  it('passes an older API body through with its own values', () => {
    const own = injury({ playerName: 'Own copy' })
    const recent = [{ gameDate: '2026-11-21', opponent: 'BOS', value: 30 }]
    const old = wireGame({ playerRecent: undefined })
    old.lines = [{ ...old.lines[0], recent, injury: own }]
    const [game] = nbaExpandPropBoard(board(old)).games
    expect(game.lines[0].recent).toBe(recent)
    expect(game.lines[0].injury).toBe(own)
    expect(game.lineOnlyLines[0]).toMatchObject({ recent: [], injury: null })
  })
})
