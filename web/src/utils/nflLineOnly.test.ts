import { describe, expect, it } from 'vitest'
import type { NflLineOnlyLine, NflLineOnlyRecent } from '~/types/nfl'
import { lineOnlyBars, lineOnlyGroups, mainRung } from '~/utils/nflLineOnly'

function recent(...values: Array<number | null>): NflLineOnlyRecent[] {
  return values.map((value, index) => ({ season: 2026, week: 3 - index, opponent: 'LV', value }))
}

function line(overrides: Partial<NflLineOnlyLine>): NflLineOnlyLine {
  return {
    playerId: 1, playerName: 'Nick Folk', position: 'K', team: 'ATL', market: 'kicking_points',
    oddsType: 'standard', line: 7.5, fetchedAt: '2026-10-05T18:00:00Z', recent: recent(9, 3, 7, 4, 6), ...overrides,
  }
}

describe('lineOnlyGroups', () => {
  it('groups by market in stored order, then one row per player sorted by name', () => {
    const groups = lineOnlyGroups([
      line({ market: 'punts', playerId: 3, playerName: 'Ryan Wright', position: 'P' }),
      line({ playerId: 2, playerName: 'Daniel Carlson' }),
      line({}),
      line({ market: 'receiving_targets', playerId: 4, playerName: 'Kyle Pitts', position: 'TE' }),
    ], 'all')

    expect(groups.map(group => group.market)).toEqual(['receiving_targets', 'kicking_points', 'punts'])
    expect(groups[1].rows.map(row => row.playerName)).toEqual(['Daniel Carlson', 'Nick Folk'])
  })

  it('collects every rung of a player line in line order', () => {
    const [group] = lineOnlyGroups([
      line({ line: 12.5, oddsType: 'demon' }), line({ line: 3.5, oddsType: 'goblin' }), line({}),
    ], 'all')

    expect(group.rows).toHaveLength(1)
    expect(group.rows[0].rungs).toEqual([
      { line: 3.5, oddsType: 'goblin' }, { line: 7.5, oddsType: 'standard' }, { line: 12.5, oddsType: 'demon' },
    ])
  })

  it('counts recent games over the standard line, a push is not over', () => {
    const [group] = lineOnlyGroups([line({ line: 6, recent: recent(9, 6, 7, 4, 6) })], 'all')

    expect(group.rows[0]).toMatchObject({ overCount: 2, count: 5 })
  })

  it('has no count without a standard line', () => {
    const [group] = lineOnlyGroups([line({ oddsType: 'goblin' }), line({ line: 9.5, oddsType: 'demon' })], 'all')

    expect(group.rows[0]).toMatchObject({ overCount: null, count: null })
  })

  it('skips games without a value', () => {
    const [group] = lineOnlyGroups([line({ recent: recent(9, null, 3) })], 'all')

    expect(group.rows[0]).toMatchObject({ overCount: 1, count: 2 })
  })

  it('keeps kickers and drops punters under K, and keeps punters under All', () => {
    const lines = [line({}), line({ market: 'punts', playerId: 3, playerName: 'Ryan Wright', position: 'P' })]

    expect(lineOnlyGroups(lines, 'K').map(group => group.market)).toEqual(['kicking_points'])
    expect(lineOnlyGroups(lines, 'all').map(group => group.market)).toEqual(['kicking_points', 'punts'])
  })

  it('is empty for no lines', () => {
    expect(lineOnlyGroups([], 'all')).toEqual([])
  })
})

describe('mainRung', () => {
  it('leads with the standard line, else the lowest rung', () => {
    expect(mainRung({ rungs: [{ line: 3.5, oddsType: 'goblin' }, { line: 7.5, oddsType: 'standard' }] }).line).toBe(7.5)
    expect(mainRung({ rungs: [{ line: 1.5, oddsType: 'goblin' }, { line: 2.5, oddsType: 'demon' }] }).line).toBe(1.5)
  })
})

describe('lineOnlyBars', () => {
  const rungs = [{ line: 5, oddsType: 'standard' }]

  it('runs oldest to newest and marks each game against the standard line', () => {
    const { bars, linePct } = lineOnlyBars({ rungs, recent: recent(10, 5, 2) })

    expect(bars.map(bar => [bar.value, bar.vsLine])).toEqual([[2, 'below'], [5, 'push'], [10, 'above']])
    expect(bars.map(bar => bar.heightPct)).toEqual([20, 50, 100])
    expect(linePct).toBe(50)
  })

  it('has no line mark without a standard line, and skips missing games', () => {
    const { bars, linePct } = lineOnlyBars({ rungs: [{ line: 1.5, oddsType: 'goblin' }], recent: recent(3, null, 1) })

    expect(bars.map(bar => [bar.value, bar.vsLine])).toEqual([[1, null], [3, null]])
    expect(linePct).toBeNull()
  })

  it('is empty without any recent value', () => {
    expect(lineOnlyBars({ rungs, recent: recent(null) })).toEqual({ bars: [], linePct: null })
  })
})
