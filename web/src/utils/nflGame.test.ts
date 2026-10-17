import { describe, expect, it } from 'vitest'
import type { NflGameOdds, NflWeather } from '~/types/nfl'
import { conditionsLabel, gameMarket, hasKickedOff, kickoffLabel, parseGameId, recordLabel } from '~/utils/nflGame'

const OUTDOOR: NflWeather = { venueType: 'outdoor', forecastFor: '2026-09-27T17:00:00Z', temperatureF: 86.4, windMph: 11.6, windGustMph: null, precipitationProbability: null, fetchedAt: null }
const ODDS: NflGameOdds = { book: 'draftkings', homeMoneyline: 120, awayMoneyline: -142, homeSpread: 2.5, total: 48.5 }

describe('parseGameId', () => {
  it('accepts a positive integer id and rejects anything else', () => {
    expect(parseGameId('40')).toBe(40)
    expect(parseGameId('abc')).toBeNull()
    expect(parseGameId('0')).toBeNull()
    expect(parseGameId(undefined)).toBeNull()
  })
})

describe('kickoffLabel', () => {
  it('reads in Central time', () => {
    expect(kickoffLabel('2026-09-27T17:00:00Z')).toBe('Sun, Sep 27, 12:00 PM CT')
  })

  it('says so when the kickoff is unknown or unparseable', () => {
    expect(kickoffLabel(null)).toBe('Kickoff time not set')
    expect(kickoffLabel('soon')).toBe('Kickoff time not set')
  })
})

describe('hasKickedOff', () => {
  const now = new Date('2026-09-27T17:00:00Z')
  it('is true at and after kickoff, false before or when unknown', () => {
    expect(hasKickedOff('2026-09-27T17:00:00Z', now)).toBe(true)
    expect(hasKickedOff('2026-09-27T18:00:00Z', now)).toBe(false)
    expect(hasKickedOff(null, now)).toBe(false)
  })
})

describe('conditionsLabel', () => {
  it('names a dome, a forecast, and a missing forecast', () => {
    expect(conditionsLabel({ ...OUTDOOR, venueType: 'dome' })).toBe('Indoor')
    expect(conditionsLabel(OUTDOOR)).toBe('86°F · wind 12 mph')
    expect(conditionsLabel({ ...OUTDOOR, forecastFor: null })).toBe('Forecast unavailable')
    expect(conditionsLabel({ ...OUTDOOR, windMph: null })).toBe('86°F · wind -- mph')
  })
})

describe('recordLabel', () => {
  it('shows wins and losses, or that no games are played', () => {
    expect(recordLabel({ games: 3, wins: 2, losses: 1, pointsForPerGame: 24, pointsAllowedPerGame: 20 })).toBe('2-1')
    expect(recordLabel(null)).toBe('No games yet')
  })
})

describe('gameMarket', () => {
  it('names the spread favorite and de-vigs the moneyline for the home side', () => {
    const market = gameMarket(ODDS, 'MIA', 'BUF')
    expect(market?.spread.value).toBe('BUF -2.5')
    expect(market?.winProbability.value).toBe('MIA 43.7%')
    expect(market?.winProbability.detail).toBe('+120 / -142 de-vigged')
    expect(market?.total.value).toBe('48.5')
  })

  it('marks missing prices and is null without odds', () => {
    const market = gameMarket({ ...ODDS, homeMoneyline: null, homeSpread: null, total: null }, 'MIA', 'BUF')
    expect([market?.spread.value, market?.winProbability.value, market?.total.value]).toEqual(['--', '--', '--'])
    expect(market?.winProbability.detail).toBe('No moneyline')
    expect(gameMarket(null, 'MIA', 'BUF')).toBeNull()
  })
})
