import { describe, expect, it } from 'vitest'
import { LEAD_TIE_WINDOW_MS, chooseLead, heroNext, nextStart, sportNoun, todayStatus, startLabel, stripOrder, stripRow, type HomeSportData } from '~/utils/home'

const HOUR = 60 * 60 * 1000
// Tue 2026-11-03 17:00 UTC = 11:00 CT.
const NOW = Date.UTC(2026, 10, 3, 17, 0)

function sportData(sport: HomeSportData['sport'], hoursFromNow: number[], overrides: Partial<HomeSportData> = {}): HomeSportData {
  return { sport, status: 'ready', gameCount: hoursFromNow.length, startsMs: hoursFromNow.map(h => NOW + h * HOUR), ...overrides }
}

describe('nextStart', () => {
  it('takes the soonest start strictly after now and ignores past and equal starts', () => {
    expect(nextStart(sportData('nba', [-2, 0, 5, 3]), NOW)).toBe(NOW + 3 * HOUR)
  })

  it('is null when nothing is left', () => {
    expect(nextStart(sportData('nba', [-1, 0]), NOW)).toBeNull()
    expect(nextStart(sportData('nba', []), NOW)).toBeNull()
  })
})

describe('chooseLead', () => {
  it('picks the sport with the nearest upcoming start', () => {
    const data = [sportData('nfl', [30]), sportData('nba', [8]), sportData('nhl', [20])]
    expect(chooseLead(data, NOW)).toBe('nba')
  })

  it('lets a team sport win a tie against a tennis start up to 3 hours earlier', () => {
    expect(chooseLead([sportData('tennis', [2]), sportData('nfl', [4])], NOW)).toBe('nfl')
    expect(LEAD_TIE_WINDOW_MS).toBe(3 * HOUR)
  })

  it('lets tennis lead when it starts more than 3 hours before every team sport', () => {
    expect(chooseLead([sportData('tennis', [1]), sportData('nfl', [5])], NOW)).toBe('tennis')
  })

  it('breaks ties between team sports in NFL, NBA, NHL order', () => {
    const data = [sportData('nhl', [4]), sportData('nba', [4]), sportData('nfl', [5])]
    expect(chooseLead(data, NOW)).toBe('nfl')
  })

  it('is null when no sport has a game to come', () => {
    const data = [sportData('nfl', [-3]), sportData('nba', []), sportData('tennis', [-1])]
    expect(chooseLead(data, NOW)).toBeNull()
  })

  it('skips a sport that is loading or errored, even with the nearest start', () => {
    const data = [sportData('nba', [1], { status: 'error' }), sportData('nhl', [2], { status: 'loading' }), sportData('nfl', [9])]
    expect(chooseLead(data, NOW)).toBe('nfl')
  })
})

describe('stripOrder', () => {
  it('drops the lead and orders the rest by first start', () => {
    const data = [sportData('tennis', [9]), sportData('nfl', [1]), sportData('nba', [3]), sportData('nhl', [2])]
    expect(stripOrder(data, 'nfl', NOW).map(entry => entry.sport)).toEqual(['nhl', 'nba', 'tennis'])
  })

  it('puts sports with nothing to come last, in registry order', () => {
    const data = [
      sportData('nhl', []), sportData('nba', [4]), sportData('tennis', [-2]), sportData('nfl', [], { status: 'error' }),
    ]
    expect(stripOrder(data, null, NOW).map(entry => entry.sport)).toEqual(['nba', 'tennis', 'nfl', 'nhl'])
  })
})

describe('stripRow', () => {
  it('describes a sport with games to come', () => {
    expect(stripRow(sportData('nba', [7, 9]), NOW)).toEqual({ sport: 'nba', text: '2 games · first tip 6:00 PM', tone: 'normal' })
    expect(stripRow(sportData('nhl', [7]), NOW).text).toBe('1 game · first puck 6:00 PM')
    expect(stripRow(sportData('tennis', [3]), NOW).text).toBe('1 match · first match 2:00 PM')
  })

  it('names the weekday when the start is not today', () => {
    expect(stripRow(sportData('nfl', [56]), NOW).text).toBe('1 game · first kickoff Thu 7:00 PM')
  })

  it('reads quiet for an empty slate, per sport', () => {
    expect(stripRow(sportData('nhl', []), NOW)).toEqual({ sport: 'nhl', text: 'No games today', tone: 'quiet' })
    expect(stripRow(sportData('tennis', []), NOW)).toEqual({ sport: 'tennis', text: 'No priced matches', tone: 'quiet' })
    expect(stripRow(sportData('nfl', []), NOW).text).toBe('No games scheduled')
    expect(stripRow(sportData('nba', []), NOW).text).toBe('No games scheduled')
  })

  it('says nothing is left when every game has started', () => {
    expect(stripRow(sportData('nba', [-3, -1]), NOW)).toEqual({ sport: 'nba', text: 'No upcoming games', tone: 'quiet' })
    expect(stripRow(sportData('tennis', [-1]), NOW).text).toBe('No upcoming matches')
  })

  it('flags a failed sport and marks a loading one', () => {
    expect(stripRow(sportData('nba', [], { status: 'error' }), NOW)).toEqual({ sport: 'nba', text: 'Could not load', tone: 'error' })
    expect(stripRow(sportData('nba', [], { status: 'loading' }), NOW)).toEqual({ sport: 'nba', text: 'Loading', tone: 'quiet' })
  })
})

describe('startLabel and heroNext', () => {
  it('uses Central time and adds the weekday only off today', () => {
    expect(startLabel(NOW + 7 * HOUR, NOW)).toBe('6:00 PM')
    expect(startLabel(NOW + 56 * HOUR, NOW)).toBe('Thu 7:00 PM')
  })

  it('words the hero line per sport', () => {
    expect(heroNext('nfl', NOW + 56 * HOUR, NOW)).toBe('Next kickoff Thu 7:00 PM CT')
    expect(heroNext('nba', NOW + 7 * HOUR, NOW)).toBe('Next tip 6:00 PM CT')
  })
})

describe('todayStatus and sportNoun', () => {
  it('leads with the Central date and time, then the lead sport', () => {
    expect(todayStatus('NFL', NOW)).toBe('Tue Nov 3 · 11:00 AM CT · NFL has the next start')
    expect(todayStatus(null, NOW)).toBe('Tue Nov 3 · 11:00 AM CT')
  })

  it('counts games or matches', () => {
    expect(sportNoun('nba', 1)).toBe('game')
    expect(sportNoun('tennis', 92)).toBe('matches')
  })
})
