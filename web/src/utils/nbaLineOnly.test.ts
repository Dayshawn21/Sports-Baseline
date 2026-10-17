import { describe, expect, it } from 'vitest'
import type { NbaLineOnlyLine, NbaLineOnlyRecent } from '~/types/nba'
import { nbaLineOnlyGroups, nbaMarketLabel, nbaRecentValueLabel } from '~/utils/nbaLineOnly'
import { lineOnlyBars } from '~/utils/nflLineOnly'

function recent(...values: Array<number | null>): NbaLineOnlyRecent[] {
  return values.map((value, index) => ({ gameDate: `2026-05-${String(20 - index).padStart(2, '0')}`, opponent: 'NY', value }))
}

function line(overrides: Partial<NbaLineOnlyLine>): NbaLineOnlyLine {
  return {
    playerId: 1, playerName: 'Jayson Tatum', position: 'F', team: 'BOS', market: 'points',
    oddsType: 'standard', line: 26.5, fetchedAt: '2026-10-06T16:30:00Z', recent: recent(30, 22, 28, 19, 31), ...overrides,
  }
}

describe('nbaLineOnlyGroups', () => {
  it('orders markets as stored, then one row per player by name', () => {
    const groups = nbaLineOnlyGroups([
      line({ market: 'double_double', line: 0.5 }),
      line({ market: 'assists', line: 5.5 }),
      line({ playerId: 2, playerName: 'Cade Cunningham', team: 'DET', position: 'G' }),
      line({}),
    ])
    expect(groups.map(group => group.market)).toEqual(['points', 'assists', 'double_double'])
    expect(groups[0].rows.map(row => [row.playerName, row.team, row.position])).toEqual([
      ['Cade Cunningham', 'DET', 'G'], ['Jayson Tatum', 'BOS', 'F'],
    ])
  })

  it('collapses a player rungs into one row in line order', () => {
    const [group] = nbaLineOnlyGroups([
      line({ line: 30.5, oddsType: 'demon' }),
      line({}),
      line({ line: 22.5, oddsType: 'goblin' }),
    ])
    expect(group.rows).toHaveLength(1)
    expect(group.rows[0].rungs).toEqual([
      { line: 22.5, oddsType: 'goblin' }, { line: 26.5, oddsType: 'standard' }, { line: 30.5, oddsType: 'demon' },
    ])
  })

  it('counts recent games strictly over the standard line and skips a null value', () => {
    const [group] = nbaLineOnlyGroups([line({ recent: recent(30, null, 26.5, 19, 31) })])
    expect(group.rows[0]).toMatchObject({ overCount: 2, count: 4 })
  })

  it('gives no count without a standard line', () => {
    const [group] = nbaLineOnlyGroups([line({ oddsType: 'goblin' })])
    expect(group.rows[0]).toMatchObject({ overCount: null, count: null })
  })

  it('keeps a player with no earlier games, with no bars', () => {
    const [group] = nbaLineOnlyGroups([line({ recent: [] })])
    expect(group.rows[0]).toMatchObject({ recent: [], overCount: 0, count: 0 })
    expect(lineOnlyBars(group.rows[0])).toEqual({ bars: [], linePct: null })
  })

  it('sorts an unknown market last and shows its raw key', () => {
    const groups = nbaLineOnlyGroups([line({ market: 'steals' }), line({ market: 'blocks', line: 0.5 })])
    expect(groups.map(group => group.market)).toEqual(['blocks', 'steals'])
    expect(nbaMarketLabel('steals')).toBe('steals')
  })
})

describe('nbaMarketLabel', () => {
  it('labels the stored markets', () => {
    expect(nbaMarketLabel('threes_made')).toBe('3-pointers made')
    expect(nbaMarketLabel('points_rebounds_assists')).toBe('Pts + reb + ast')
    expect(nbaMarketLabel('double_double')).toBe('Double-double')
  })
})

describe('nbaRecentValueLabel', () => {
  it('reads double-double as yes or no and other markets as numbers', () => {
    expect(nbaRecentValueLabel('double_double', 1)).toBe('yes')
    expect(nbaRecentValueLabel('double_double', 0)).toBe('no')
    expect(nbaRecentValueLabel('points', 28)).toBe('28')
    expect(nbaRecentValueLabel('points', null)).toBe('--')
  })

  it('bars double-double results against its stored line', () => {
    const [group] = nbaLineOnlyGroups([line({ market: 'double_double', line: 0.5, recent: recent(1, 0, 1) })])
    expect(group.rows[0]).toMatchObject({ overCount: 2, count: 3 })
    expect(lineOnlyBars(group.rows[0]).bars.map(bar => bar.vsLine)).toEqual(['above', 'below', 'above'])
  })
})
