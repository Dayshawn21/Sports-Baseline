import { describe, expect, it } from 'vitest'
import type { NhlProjectionHistoryPoint } from '~/types/nhl'
import {
  filterNhlHistory, nhlHistoryDefaultStat, nhlHistoryFilterOptions, nhlHistorySearch, nhlHistoryStatOptions,
  nhlHistoryValueLabel, nhlSeasonLabel, parseNhlHistoryParams,
} from '~/utils/nhlProjectionHistory'

function point(overrides: Partial<NhlProjectionHistoryPoint> = {}): NhlProjectionHistoryPoint {
  return {
    gameId: 1, gameDate: '2026-11-07', season: 2026, opponentId: 14, opponentName: 'TBL',
    stat: 'shots_on_goal', line: 3, projection: 2.9, actual: 5, snapshotAt: '2026-11-08T00:47:54Z', ...overrides,
  }
}

const POINTS = [
  point({ gameId: 3, gameDate: '2026-11-10', opponentId: 15, opponentName: 'MTL', line: 3.5, actual: 1 }),
  point({ gameId: 1 }),
  point({ gameId: 2, gameDate: '2027-10-09', season: 2027, opponentId: 15, opponentName: 'MTL' }),
  point({ gameId: 1, stat: 'time_on_ice', line: 21.75, projection: null, actual: 20.43 }),
  point({ gameId: 4, stat: 'goalie_saves', opponentId: 16, opponentName: 'NSH', line: 21.5, actual: 22 }),
]

describe('nhlSeasonLabel', () => {
  it('names a season by its start and end years', () => {
    expect(nhlSeasonLabel(2026)).toBe('2026-27')
    expect(nhlSeasonLabel(2099)).toBe('2099-00')
  })
})

describe('nhlHistoryValueLabel', () => {
  it('keeps two decimals for time on ice so a quarter-minute line and its projection stay apart', () => {
    expect(nhlHistoryValueLabel('time_on_ice', 21.75)).toBe('21.75')
    expect(nhlHistoryValueLabel('time_on_ice', 21.79)).toBe('21.79')
    expect(nhlHistoryValueLabel('time_on_ice', 20.4)).toBe('20.4')
  })

  it('signs plus/minus and prints counts as they are', () => {
    expect(nhlHistoryValueLabel('plus_minus', 2)).toBe('+2')
    expect(nhlHistoryValueLabel('plus_minus', -1)).toBe('-1')
    expect(nhlHistoryValueLabel('goalie_saves', 22)).toBe('22')
  })
})

describe('nhlHistoryStatOptions', () => {
  it('orders markets by points charted, then label', () => {
    expect(nhlHistoryStatOptions(POINTS).map(option => [option.stat, option.count, option.label])).toEqual([
      ['shots_on_goal', 3, 'Shots on Goal'], ['goalie_saves', 1, 'Goalie Saves'], ['time_on_ice', 1, 'Time On Ice'],
    ])
  })

  it('has no options for an empty history', () => {
    expect(nhlHistoryStatOptions([])).toEqual([])
  })
})

describe('nhlHistoryFilterOptions', () => {
  it('lists the seasons newest first and opponents most faced first', () => {
    const options = nhlHistoryFilterOptions(POINTS, 'shots_on_goal')
    expect(options.seasons).toEqual([{ season: 2027, label: '2027-28' }, { season: 2026, label: '2026-27' }])
    expect(options.opponents).toEqual([{ id: 15, name: 'MTL', count: 2 }, { id: 14, name: 'TBL', count: 1 }])
  })

  it('reads only the chosen stat, so a goalie market has its own opponents', () => {
    expect(nhlHistoryFilterOptions(POINTS, 'goalie_saves').opponents).toEqual([{ id: 16, name: 'NSH', count: 1 }])
    expect(nhlHistoryFilterOptions(POINTS, null)).toEqual({ seasons: [], opponents: [] })
  })
})

describe('filterNhlHistory', () => {
  it('keeps one stat oldest game first', () => {
    expect(filterNhlHistory(POINTS, { stat: 'shots_on_goal', season: null, opponentId: null }).map(p => p.gameId)).toEqual([1, 3, 2])
  })

  it('applies the season and opponent filters', () => {
    expect(filterNhlHistory(POINTS, { stat: 'shots_on_goal', season: 2026, opponentId: null }).map(p => p.gameId)).toEqual([1, 3])
    expect(filterNhlHistory(POINTS, { stat: 'shots_on_goal', season: 2026, opponentId: 15 }).map(p => p.gameId)).toEqual([3])
  })

  it('keeps a point whose frozen projection is null', () => {
    const [shown] = filterNhlHistory(POINTS, { stat: 'time_on_ice', season: null, opponentId: null })
    expect(shown.projection).toBeNull()
    expect(shown.actual).toBe(20.43)
  })
})

describe('nhlHistoryDefaultStat', () => {
  it('prefers the open market tab when it has history', () => {
    expect(nhlHistoryDefaultStat(POINTS, 'goalie_saves')).toBe('goalie_saves')
  })

  it('falls back to the most charted stat for a tab without history or an unknown market', () => {
    expect(nhlHistoryDefaultStat(POINTS, 'hits')).toBe('shots_on_goal')
    expect(nhlHistoryDefaultStat(POINTS, 'aces')).toBe('shots_on_goal')
    expect(nhlHistoryDefaultStat([], 'hits')).toBeNull()
  })
})

describe('parseNhlHistoryParams', () => {
  it('reads a known stat, season and opponent', () => {
    const params = new URLSearchParams('hstat=shots_on_goal&hseason=2026&hopp=15')
    expect(parseNhlHistoryParams(params, POINTS)).toEqual({ stat: 'shots_on_goal', season: 2026, opponentId: 15 })
  })

  it('falls back from an unknown stat to the market tab, then the first option', () => {
    expect(parseNhlHistoryParams(new URLSearchParams('hstat=aces'), POINTS, 'time_on_ice').stat).toBe('time_on_ice')
    expect(parseNhlHistoryParams(new URLSearchParams('hstat=aces'), POINTS).stat).toBe('shots_on_goal')
  })

  it('drops a season or opponent the chosen stat has no point for', () => {
    const params = new URLSearchParams('hstat=goalie_saves&hseason=2027&hopp=15')
    expect(parseNhlHistoryParams(params, POINTS)).toEqual({ stat: 'goalie_saves', season: null, opponentId: null })
    expect(parseNhlHistoryParams(new URLSearchParams('hseason=abc&hopp='), POINTS)).toEqual({
      stat: 'shots_on_goal', season: null, opponentId: null,
    })
  })
})

describe('nhlHistorySearch', () => {
  it('writes the filters and leaves the page params alone', () => {
    const params = new URLSearchParams('date=2026-11-10&market=points')
    expect(nhlHistorySearch(params, { stat: 'time_on_ice', season: 2026, opponentId: 14 }, 'shots_on_goal'))
      .toBe('?date=2026-11-10&market=points&hstat=time_on_ice&hseason=2026&hopp=14')
  })

  it('drops the default stat and cleared filters', () => {
    const params = new URLSearchParams('market=points&hstat=hits&hseason=2026&hopp=14')
    expect(nhlHistorySearch(params, { stat: 'shots_on_goal', season: null, opponentId: null }, 'shots_on_goal')).toBe('?market=points')
  })
})
