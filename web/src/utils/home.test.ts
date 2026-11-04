import { describe, expect, it } from 'vitest'
import type { HomeSource } from '~/utils/homeSources'
import { homeCard, newestUpdate, nextStart, sportNoun, startLabel, todayStatus, type HomeSportData } from '~/utils/home'

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

describe('startLabel', () => {
  it('uses Central time and adds the weekday only off today', () => {
    expect(startLabel(NOW + 7 * HOUR, NOW)).toBe('6:00 PM')
    expect(startLabel(NOW + 56 * HOUR, NOW)).toBe('Thu 7:00 PM')
  })

})

describe('todayStatus and sportNoun', () => {
  it('leads with the Central date and time, then when the newest slate loaded', () => {
    expect(todayStatus(NOW, NOW - 30 * 60 * 1000)).toBe('Tue Nov 3 · 11:00 AM CT · slates refreshed 10:30 AM')
    expect(todayStatus(NOW, null)).toBe('Tue Nov 3 · 11:00 AM CT')
  })

  it('takes the newest load time and ignores slates that have not loaded', () => {
    expect(newestUpdate([0, 5, 9, 0])).toBe(9)
    expect(newestUpdate([0, 0])).toBeNull()
    expect(newestUpdate([])).toBeNull()
  })

  it('counts games or matches', () => {
    expect(sportNoun('nba', 1)).toBe('game')
    expect(sportNoun('tennis', 92)).toBe('matches')
  })
})

const source = (overrides: Partial<HomeSource> = {}): HomeSource => ({
  gameCount: 0, startsMs: [], propLines: null, gaps: [], nextGames: [], period: null, days: [], ...overrides,
})
const game = (key: string, title: string) => ({ key, title, when: '' })

describe('homeCard', () => {
  it('describes the NFL week with its days', () => {
    const days = [
      { key: 'a', label: 'Thu', count: 1, title: 'JAX @ BAL' },
      { key: 'b', label: 'Sun', count: 12, title: 'x' },
      { key: 'c', label: 'Mon', count: 1, title: 'DEN @ CAR' },
    ]
    const card = homeCard(sportData('nfl', [56, 100]), source({ period: 'Week 9', days }), NOW)
    expect(card).toMatchObject({
      sport: 'nfl', label: 'NFL', period: 'WEEK 9', when: 'Next kickoff Thu 7:00 PM CT', count: '2', noun: 'games', tone: 'normal',
      next: 'Thu: JAX @ BAL · Sun: 12 games · Mon: DEN @ CAR',
    })
    expect(card.links.map(link => [link.label, link.path])).toEqual([['Slate', '/nfl'], ['Props', '/nfl/board'], ['Model', '/nfl/model']])
  })

  it('lists the next games for a day-based sport and tags it TODAY', () => {
    const next = [game('1', 'ORL @ CHA'), game('2', 'DET @ TOR'), game('3', 'LAL @ GSW')]
    const card = homeCard(sportData('nba', [7, 9]), source({ nextGames: next }), NOW)
    expect(card).toMatchObject({ period: 'TODAY', when: 'First tip 6:00 PM CT', count: '2', next: 'Next: ORL @ CHA, DET @ TOR, LAL @ GSW' })
    expect(homeCard(sportData('nhl', [7]), source(), NOW)).toMatchObject({ when: 'First puck 6:00 PM CT', next: '' })
  })

  it('gives NHL only a Slate link and tennis all three', () => {
    expect(homeCard(sportData('nhl', [7]), source(), NOW).links.map(link => link.label)).toEqual(['Slate'])
    expect(homeCard(sportData('tennis', [3]), source(), NOW).links.map(link => link.label)).toEqual(['Slate', 'Props', 'Model'])
  })

  it('counts priced matches for tennis and singular nouns', () => {
    expect(homeCard(sportData('tennis', [3, 4]), source(), NOW)).toMatchObject({ when: 'First match 2:00 PM CT', noun: 'matches priced' })
    expect(homeCard(sportData('nba', [3]), source(), NOW).noun).toBe('game')
  })

  it('goes quiet with its own text when the slate is empty', () => {
    expect(homeCard(sportData('nhl', []), source(), NOW)).toMatchObject({ when: 'No games today', count: '0', tone: 'quiet', next: '' })
    expect(homeCard(sportData('nfl', []), source(), NOW).when).toBe('No games scheduled')
    expect(homeCard(sportData('nba', []), source(), NOW).when).toBe('No games scheduled')
    expect(homeCard(sportData('tennis', []), source(), NOW)).toMatchObject({ when: 'No priced matches', tone: 'quiet' })
  })

  it('says nothing is left when every game has started', () => {
    expect(homeCard(sportData('nba', [-3, -1]), source(), NOW)).toMatchObject({ when: 'No upcoming games', count: '2', tone: 'quiet' })
    expect(homeCard(sportData('tennis', [-1]), source(), NOW).when).toBe('No upcoming matches')
  })

  it('marks a loading or failed sport without a made-up count', () => {
    expect(homeCard(sportData('nba', [], { status: 'loading' }), source(), NOW)).toMatchObject({ when: 'Loading', count: '--', tone: 'loading', next: '' })
    expect(homeCard(sportData('nba', [], { status: 'error' }), source(), NOW)).toMatchObject({ when: 'Could not load', count: '--', tone: 'error' })
  })
})
