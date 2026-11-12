import { describe, expect, it } from 'vitest'
import type { NbaInjury, NbaInjuryReport } from '~/types/nba'
import { activeOutFilter, filterTeammateOut, parseOutFilter, teammateOutOptions, type NbaTeammateOutOption } from '~/utils/nbaTeammateOut'
import { ALL, filterBoardMarkets } from '~/utils/propFilters'

const FETCHED = '2026-11-11T20:00:00Z'

function injury(overrides: Partial<NbaInjury> = {}): NbaInjury {
  return {
    espnAthleteId: '3059318', playerId: 7, playerName: 'Joel Embiid', team: 'PHI', athleteTeam: 'PHI',
    status: 'Out', detail: 'Knee', sourceUpdatedAt: FETCHED, returnDate: null, fetchedAt: FETCHED, ...overrides,
  }
}

function report(injuries: NbaInjury[], freshness: NbaInjuryReport['freshness'] = 'fresh'): NbaInjuryReport {
  return { source: 'ESPN', fetchedAt: FETCHED, freshness, injuries }
}

function game(gameId: number, awayTeam: string, homeTeam: string, injuries: NbaInjury[] = [], freshness: NbaInjuryReport['freshness'] = 'fresh') {
  return { gameId, awayTeam, homeTeam, injuryReport: report(injuries, freshness) }
}

const PHI_BOS = game(1, 'PHI', 'BOS')
const PHX_LAL = game(2, 'PHX', 'LAL')

function row(gameRef: { gameId: number, awayTeam: string, homeTeam: string }, playerId: number, team: string | null, playerName = `Player ${playerId}`) {
  return { key: `${gameRef.gameId}:${playerId}`, game: gameRef, row: { playerId, playerName, team } }
}

function option(overrides: Partial<NbaTeammateOutOption> = {}): NbaTeammateOutOption {
  return { id: '3059318', playerId: 7, playerName: 'Joel Embiid', team: 'PHI', gameId: 1, status: 'Out', stale: false, ...overrides }
}

describe('teammateOutOptions', () => {
  it('keeps Out and Suspension in any letter case and drops Day-To-Day', () => {
    const options = teammateOutOptions([game(1, 'PHI', 'BOS', [
      injury(),
      injury({ espnAthleteId: '2', playerName: 'Kelly Oubre', status: 'SUSPENSION' }),
      injury({ espnAthleteId: '3', playerName: 'Tyrese Maxey', status: 'out' }),
      injury({ espnAthleteId: '4', playerName: 'Paul George', status: 'Day-To-Day' }),
    ])])
    expect(options.map(item => item.id)).toEqual(['3059318', '2', '3'])
  })

  it('drops an athlete ESPN lists on another team and an entry on neither side', () => {
    const options = teammateOutOptions([game(1, 'PHI', 'BOS', [
      injury({ athleteTeam: 'MIA' }),
      injury({ espnAthleteId: '2', team: 'NYK', athleteTeam: 'NYK' }),
      injury({ espnAthleteId: '3', playerName: 'Jayson Tatum', team: 'BOS', athleteTeam: null }),
    ])])
    expect(options.map(item => item.id)).toEqual(['3'])
  })

  it('gives no options from an unavailable report and marks a stale one', () => {
    expect(teammateOutOptions([game(1, 'PHI', 'BOS', [injury()], 'unavailable')])).toEqual([])
    expect(teammateOutOptions([game(1, 'PHI', 'BOS', [injury()], 'stale')])[0].stale).toBe(true)
    expect(teammateOutOptions([game(1, 'PHI', 'BOS', [injury()])])[0].stale).toBe(false)
  })

  it('sorts by team then name and lists a repeated entry once per game', () => {
    const options = teammateOutOptions([
      game(1, 'PHI', 'BOS', [injury(), injury(), injury({ espnAthleteId: '9', playerName: 'Jrue Holiday', team: 'BOS', athleteTeam: 'BOS' })]),
      game(2, 'PHX', 'LAL', [injury({ espnAthleteId: '5', playerName: 'Bradley Beal', team: 'PHX', athleteTeam: 'PHX' })]),
    ])
    expect(options.map(item => [item.team, item.playerName, item.gameId])).toEqual([
      ['BOS', 'Jrue Holiday', 1], ['PHI', 'Joel Embiid', 1], ['PHX', 'Bradley Beal', 2],
    ])
  })
})

describe('out filter param', () => {
  const options = [option()]

  it('reads digits only and resolves only ids that are out on this board', () => {
    expect(parseOutFilter(new URLSearchParams('out=3059318'))).toBe('3059318')
    expect(parseOutFilter(new URLSearchParams('out=embiid'))).toBeNull()
    expect(parseOutFilter(new URLSearchParams())).toBeNull()
    expect(activeOutFilter('3059318', options)?.playerName).toBe('Joel Embiid')
    expect(activeOutFilter('42', options)).toBeNull()
    expect(activeOutFilter(null, options)).toBeNull()
  })
})

describe('filterTeammateOut', () => {
  const markets = [
    { market: 'points', rows: [row(PHI_BOS, 7, 'PHI'), row(PHI_BOS, 11, 'PHI'), row(PHI_BOS, 20, 'BOS'), row(PHX_LAL, 30, 'PHX')] },
    { market: 'assists', rows: [row(PHI_BOS, 20, 'BOS')] },
  ]

  it('keeps only the teammates in that game and every market, emptied ones included', () => {
    const filtered = filterTeammateOut(markets, option())
    expect(filtered.map(item => [item.market, item.rows.map(entry => entry.row.playerId)])).toEqual([['points', [11]], ['assists', []]])
  })

  it('matches a PrizePicks code that differs from the game code', () => {
    const phx = filterTeammateOut([{ market: 'points', rows: [row(PHX_LAL, 30, 'PHO'), row(PHX_LAL, 31, 'LAL')] }],
      option({ id: '5', playerId: 99, team: 'PHX', gameId: 2 }))
    expect(phx[0].rows.map(entry => entry.row.playerId)).toEqual([30])
  })

  it('drops nobody by id when the out player is not linked', () => {
    const filtered = filterTeammateOut(markets, option({ playerId: null }))
    expect(filtered[0].rows.map(entry => entry.row.playerId)).toEqual([7, 11])
  })

  it('returns the markets unchanged with no option and composes after the board filters', () => {
    expect(filterTeammateOut(markets, null)).toBe(markets)
    const named = filterBoardMarkets(markets, { players: ['Player 11'], team: ALL, games: [] })
    expect(filterTeammateOut(named, option())[0].rows.map(entry => entry.row.playerId)).toEqual([11])
  })
})
