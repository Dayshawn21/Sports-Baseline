import { describe, expect, it } from 'vitest'
import type { HomeGap, HomeSource } from '~/utils/homeSources'
import {
  allGapRows, gapTabs, gapsBody, homeCard, newestUpdate, nextStart, parseGapTab, sportNoun, startLabel, todayStatus,
  type HomeSportData, type HomeSportView,
} from '~/utils/home'

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
  gameCount: 0, startsMs: [], propLines: null, gaps: [], nextGames: [], schedule: [], period: null, days: [], ...overrides,
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

describe('gaps tabs', () => {
  const gap = (sport: HomeGap['sport'], key: string): HomeGap => ({
    key, sport, playerName: key, market: 'm', matchup: 'A @ B', when: 'w', line: '1', model: '2', gap: 'g', path: `/p/${key}`,
  })
  const view = (sport: HomeSportData['sport'], hours: number[], overrides: Partial<HomeSource> = {}, data: Partial<HomeSportData> = {}): HomeSportView => ({
    data: sportData(sport, hours, data), source: source({ gameCount: hours.length, ...overrides }),
  })
  const sports = (): HomeSportView[] => [
    view('nfl', [56], { gaps: [gap('nfl', 'f1'), gap('nfl', 'f2')] }),
    view('nba', [7], { gaps: [gap('nba', 'b1')] }),
    view('nhl', [], { schedule: [{ key: '1', title: 'A @ B', when: '6:00 PM' }] }),
    view('tennis', [], {}, { status: 'loading' }),
  ]

  it('lists All then each sport in the cards order, with the next start on a sport that has one', () => {
    expect(gapTabs(sports(), NOW).map(tab => [tab.key, tab.text])).toEqual([
      ['all', 'All'], ['nfl', 'NFL · Thu 7:00 PM'], ['nba', 'NBA · 6:00 PM'], ['nhl', 'NHL'], ['tennis', 'Tennis'],
    ])
  })

  it('shows no start when the sport has nothing left or has not loaded', () => {
    const list = sports()
    list[1] = view('nba', [-3])
    list[0] = view('nfl', [56], {}, { status: 'error' })
    expect(gapTabs(list, NOW).map(tab => tab.text)).toEqual(['All', 'NFL', 'NBA', 'NHL', 'Tennis'])
  })

  it('reads a missing or unknown tab as All', () => {
    expect(parseGapTab(null)).toBe('all')
    expect(parseGapTab('golf')).toBe('all')
    expect(parseGapTab('nba')).toBe('nba')
  })

  it('puts NFL rows before NBA rows and never sorts across sports', () => {
    expect(allGapRows(sports()).map(row => row.key)).toEqual(['f1', 'f2', 'b1'])
  })

  it('gives a sport tab its own rows and a link to the props board', () => {
    expect(gapsBody('nba', sports())).toMatchObject({
      kind: 'rows', rows: [{ key: 'b1' }], footer: { label: 'View all NBA props', path: '/nba/board' },
    })
  })

  it('says why a sport tab is empty, including a failed gap query', () => {
    const noGaps = [view('nfl', [], {}), ...sports().slice(1)]
    expect(gapsBody('nfl', noGaps)).toMatchObject({ rows: [], empty: 'No games scheduled' })
    const quiet = [view('nfl', [56]), ...sports().slice(1)]
    expect(gapsBody('nfl', quiet)).toMatchObject({ empty: 'No gap lines yet.' })
    const failed = [...sports().slice(0, 1), view('nba', [7], { gapsFailed: true }), ...sports().slice(2)]
    expect(gapsBody('nba', failed)).toMatchObject({ rows: [], empty: 'Gap lines could not load.' })
  })

  it('lists next games for NHL, and says why, with a slate link', () => {
    expect(gapsBody('nhl', sports())).toMatchObject({
      kind: 'games', games: [{ key: '1' }], footer: { label: 'Open the NHL slate', path: '/nhl' },
      intro: expect.stringContaining('no gaps to show'),
    })
  })

  it('shows a loading or failed sport as such', () => {
    expect(gapsBody('tennis', sports())).toEqual({ kind: 'loading' })
    const list = sports()
    list[0] = view('nfl', [], {}, { status: 'error' })
    expect(gapsBody('nfl', list)).toEqual({ kind: 'error', text: 'Could not load' })
  })
})
