import { describe, expect, it } from 'vitest'
import type { NbaSlateGame } from '~/types/nba'
import { nbaGameMarket, parseGameId } from '~/utils/nbaGame'

const FETCHED = '2026-10-06T14:34:47Z'

function game(overrides: Partial<NbaSlateGame> = {}): NbaSlateGame {
  return {
    gameId: 21320, season: 2026, week: 1, gameType: 'REG', gameDate: '2026-10-20', startUtc: '2026-10-20T23:00:00Z',
    status: 'scheduled', awayTeam: 'BOS', homeTeam: 'DET', awayTeamName: 'Boston Celtics', homeTeamName: 'Detroit Pistons',
    awayScore: null, homeScore: null, awayRecord: { wins: 0, losses: 0 }, homeRecord: { wins: 0, losses: 0 }, propLineCount: 61,
    moneyline: { book: 'draftkings', homeOdds: -125, awayOdds: 105, homeWinProbability: 0.532, fetchedAt: FETCHED },
    spread: { book: 'draftkings', homeLine: -2.5, homeOdds: -105, awayOdds: -115, fetchedAt: FETCHED },
    total: { book: 'draftkings', line: 221.5, overOdds: -110, underOdds: -110, fetchedAt: FETCHED },
    lineMovement: [],
    ...overrides,
  }
}

describe('nbaGameMarket', () => {
  it('leads every cell with the home favorite', () => {
    expect(nbaGameMarket(game())).toEqual({
      spread: { value: 'DET -2.5', detail: '-105 / -115 · draftkings' },
      winProbability: { value: 'DET 53.2%', detail: 'DET -125 / BOS +105 de-vigged · draftkings' },
      total: { value: '221.5', detail: 'o -110 / u -110 · draftkings' },
    })
  })

  it('leads with an away favorite', () => {
    const market = nbaGameMarket(game({
      moneyline: { book: 'draftkings', homeOdds: 154, awayOdds: -185, homeWinProbability: 0.38, fetchedAt: FETCHED },
      spread: { book: 'draftkings', homeLine: 5.5, homeOdds: -112, awayOdds: -108, fetchedAt: FETCHED },
    }))
    expect(market?.spread).toEqual({ value: 'BOS -5.5', detail: '-108 / -112 · draftkings' })
    expect(market?.winProbability).toEqual({ value: 'BOS 62.0%', detail: 'BOS -185 / DET +154 de-vigged · draftkings' })
  })

  it('shows a pick-em spread and a 50/50 moneyline from the home side', () => {
    const market = nbaGameMarket(game({
      moneyline: { book: 'draftkings', homeOdds: -110, awayOdds: -110, homeWinProbability: 0.5, fetchedAt: FETCHED },
      spread: { book: 'draftkings', homeLine: 0, homeOdds: -110, awayOdds: -110, fetchedAt: FETCHED },
    }))
    expect(market?.spread.value).toBe('PK')
    expect(market?.winProbability).toEqual({ value: 'DET 50.0%', detail: 'DET -110 / BOS -110 de-vigged · draftkings' })
  })

  it('marks each missing market alone as not stored', () => {
    const missing = { value: '--', detail: 'Not stored' }
    expect(nbaGameMarket(game({ spread: null }))?.spread).toEqual(missing)
    expect(nbaGameMarket(game({ moneyline: null }))?.winProbability).toEqual(missing)
    expect(nbaGameMarket(game({ total: null }))?.total).toEqual(missing)
    expect(nbaGameMarket(game({ total: null }))?.spread.value).toBe('DET -2.5')
  })

  it('is null when no market is stored', () => {
    expect(nbaGameMarket(game({ moneyline: null, spread: null, total: null }))).toBeNull()
  })

  it('names the book on each cell when markets come from different books', () => {
    const market = nbaGameMarket(game({
      spread: { book: 'fanduel', homeLine: -2.5, homeOdds: -110, awayOdds: -110, fetchedAt: FETCHED },
      total: { book: 'betmgm', line: 220.5, overOdds: -105, underOdds: -115, fetchedAt: FETCHED },
    }))
    expect(market?.spread.detail).toBe('-110 / -110 · fanduel')
    expect(market?.winProbability.detail).toMatch(/· draftkings$/)
    expect(market?.total.detail).toBe('o -105 / u -115 · betmgm')
  })
})

describe('parseGameId', () => {
  it('accepts a positive integer id only', () => {
    expect(parseGameId('21320')).toBe(21320)
    expect(parseGameId('abc')).toBeNull()
    expect(parseGameId(undefined)).toBeNull()
  })
})
