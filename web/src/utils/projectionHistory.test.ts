import { describe, expect, it } from 'vitest'
import type { ProjectionHistoryPoint } from '~/types/tennis'
import {
  filterHistory, historyDefaultStat, historyFilterOptions, historyScale, historySearch, historyStatOptions, parseHistoryParams,
} from '~/utils/projectionHistory'
import { marketKey } from '~/utils/tennisPropBoard'

function point(overrides: Partial<ProjectionHistoryPoint> = {}): ProjectionHistoryPoint {
  return {
    matchId: 1, matchDate: '2026-10-02', tournament: 'Shanghai', round: 'R32', surface: 'Hard',
    opponentId: 40, opponentName: 'Ben Shelton', stat: 'aces', line: 7.5, projection: 8.1, actual: 9,
    snapshotAt: '2026-10-01T12:00:00Z', ...overrides,
  }
}

const POINTS = [
  point({ matchId: 3, matchDate: '2026-10-20', stat: 'aces', surface: 'Clay', opponentId: 41, opponentName: 'Casper Ruud' }),
  point({ matchId: 1, matchDate: '2026-10-02', stat: 'aces' }),
  point({ matchId: 2, matchDate: '2026-10-10', stat: 'aces', opponentId: 41, opponentName: 'Casper Ruud' }),
  point({ matchId: 2, matchDate: '2026-10-10', stat: 'total_games', line: 22.5, projection: null, actual: 25 }),
  point({ matchId: 4, matchDate: '2026-10-12', stat: 'double_faults' }),
]

describe('historyStatOptions', () => {
  it('orders stats by points charted, then label', () => {
    expect(historyStatOptions(POINTS).map(option => [option.stat, option.count])).toEqual([
      ['aces', 3], ['double_faults', 1], ['total_games', 1],
    ])
    expect(historyStatOptions(POINTS)[0].label).toBe('Aces')
  })

  it('keys a stored stat the same way the board keys its stat type', () => {
    expect(historyStatOptions([point({ stat: 'break_points_won' })])[0].stat).toBe(marketKey('Break Points Won'))
  })

  it('is empty with no points', () => {
    expect(historyStatOptions([])).toEqual([])
  })
})

describe('historyFilterOptions', () => {
  it('lists the surfaces and opponents one stat has, opponents faced most first', () => {
    const options = historyFilterOptions(POINTS, 'aces')
    expect(options.surfaces).toEqual(['Clay', 'Hard'])
    expect(options.opponents.map(o => [o.name, o.count])).toEqual([['Casper Ruud', 2], ['Ben Shelton', 1]])
  })

  it('has nothing for no stat', () => {
    expect(historyFilterOptions(POINTS, null)).toEqual({ surfaces: [], opponents: [] })
  })
})

describe('filterHistory', () => {
  it('keeps one stat, oldest match first', () => {
    expect(filterHistory(POINTS, { stat: 'aces', surface: null, opponentId: null }).map(p => p.matchId)).toEqual([1, 2, 3])
  })

  it('applies surface (any case) and opponent together', () => {
    expect(filterHistory(POINTS, { stat: 'aces', surface: 'hard', opponentId: 41 }).map(p => p.matchId)).toEqual([2])
  })
})

describe('historyScale', () => {
  it('puts result, line and projection on one shared max', () => {
    const [column] = historyScale([point({ actual: 10, line: 5, projection: 2.5 })])
    expect(column).toMatchObject({ actualPct: 100, linePct: 50, projectionPct: 25 })
  })

  it('says which side of its own line each result landed', () => {
    const sides = historyScale([point({ actual: 9 }), point({ actual: 6 }), point({ actual: 7.5 })]).map(c => c.vsLine)
    expect(sides).toEqual(['above', 'below', 'push'])
  })

  it('keeps a missing projection missing', () => {
    expect(historyScale([point({ projection: null })])[0].projectionPct).toBeNull()
  })

  it('gives zero heights, not NaN, for an all-zero sample', () => {
    const [column] = historyScale([point({ actual: 0, line: 0, projection: 0 })])
    expect(column).toMatchObject({ actualPct: 0, linePct: 0, projectionPct: 0 })
  })
})

describe('parseHistoryParams', () => {
  it('reads a known stat, surface and opponent', () => {
    expect(parseHistoryParams(new URLSearchParams('hstat=aces&hsurface=clay&hopp=41'), POINTS))
      .toEqual({ stat: 'aces', surface: 'Clay', opponentId: 41 })
  })

  it('falls back to the open market tab, then the first option, for an unknown stat', () => {
    expect(parseHistoryParams(new URLSearchParams('hstat=nope'), POINTS, 'total_games').stat).toBe('total_games')
    expect(parseHistoryParams(new URLSearchParams('hstat=nope'), POINTS, 'moneyline').stat).toBe('aces')
  })

  it('drops a surface or opponent the chosen stat has no point for', () => {
    expect(parseHistoryParams(new URLSearchParams('hstat=double_faults&hsurface=clay&hopp=41'), POINTS))
      .toEqual({ stat: 'double_faults', surface: null, opponentId: null })
  })

  it('has no stat with no points', () => {
    expect(parseHistoryParams(new URLSearchParams(), [])).toEqual({ stat: null, surface: null, opponentId: null })
  })
})

describe('historyDefaultStat', () => {
  it('prefers the open market tab, then the most charted stat', () => {
    expect(historyDefaultStat(POINTS, 'Total Games')).toBe('total_games')
    expect(historyDefaultStat(POINTS, 'moneyline')).toBe('aces')
    expect(historyDefaultStat([], 'aces')).toBeNull()
  })

  it('round-trips the first stat while a different market tab is open', () => {
    const params = new URLSearchParams('market=total_games&hstat=total_games')
    const defaultStat = historyDefaultStat(POINTS, params.get('market'))
    const search = historySearch(params, { stat: 'aces', surface: null, opponentId: null }, defaultStat)
    expect(parseHistoryParams(new URLSearchParams(search.slice(1)), POINTS, 'total_games').stat).toBe('aces')
  })
})

describe('historySearch', () => {
  it('writes the filters and keeps the page params', () => {
    const params = new URLSearchParams('market=aces&form=10')
    expect(historySearch(params, { stat: 'total_games', surface: 'Hard', opponentId: 40 }, 'aces'))
      .toBe('?market=aces&form=10&hstat=total_games&hsurface=hard&hopp=40')
  })

  it('drops the default stat and cleared filters', () => {
    const params = new URLSearchParams('hstat=total_games&hsurface=hard&hopp=40')
    expect(historySearch(params, { stat: 'aces', surface: null, opponentId: null }, 'aces')).toBe('?')
  })
})
