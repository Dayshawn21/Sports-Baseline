import { describe, expect, it } from 'vitest'
import type { NflOtherMarket, NflOtherMarketGame } from '~/types/nfl'
import { formOptions, formSample } from '~/utils/nflFormWindow'
import { notLoadedCount, otherMarketFormRow, otherMarketSample, playerTabs, standardLine } from '~/utils/nflOtherMarkets'

const game = (week: number, value: number | null, opponent = 'MIA'): NflOtherMarketGame => ({ season: 2026, week, gameDate: `2026-10-${String(week).padStart(2, '0')}`, opponent, value })

function market(overrides: Partial<NflOtherMarket> = {}): NflOtherMarket {
  return {
    market: 'interceptions', gameId: 1,
    lines: [{ line: 0.5, oddsType: 'standard', fetchedAt: '2026-11-01T12:00:00Z' }],
    recent: Array.from({ length: 10 }, (_, index) => game(20 - index, index)),
    opponentGames: [game(3, 2, 'CLE'), game(1, null, 'CLE')],
    ...overrides,
  }
}

describe('otherMarketSample', () => {
  it('drops a game whose stat was not loaded instead of drawing a zero', () => {
    const sample = otherMarketSample([game(3, 2), game(2, null), game(1, 4)])
    expect(sample.values.map(item => item.value)).toEqual([2, 4])
    expect(sample.average).toBe(3)
  })

  it('has no average for an empty sample and carries the game date', () => {
    expect(otherMarketSample([]).average).toBeNull()
    expect(otherMarketSample([game(3, 2)]).values[0].gameDate).toBe('2026-10-03')
  })
})

describe('otherMarketFormRow', () => {
  it('makes Last 5 the first five of Last 10', () => {
    const row = otherMarketFormRow(market(), 'CLE')
    expect(row.recentForm.values).toEqual(row.recentFormLong?.values.slice(0, 5))
    expect(formSample(row, '10').values).toHaveLength(10)
    expect(formSample(row, 'opp').values.map(item => item.value)).toEqual([2])
  })

  it('disables vs Opponent through the shared options when the opponent is unknown', () => {
    const options = formOptions(otherMarketFormRow(market({ opponentGames: [] }), null))
    expect(options.map(option => option.disabledReason)).toEqual([null, null, 'No opponent this week'])
  })
})

describe('notLoadedCount', () => {
  it('counts per window', () => {
    const m = market({ recent: [game(5, null), game(4, 1), game(3, 1), game(2, 1), game(1, 1), game(0, null)] })
    expect([notLoadedCount(m, '5'), notLoadedCount(m, '10'), notLoadedCount(m, 'opp')]).toEqual([1, 2, 1])
  })
})

describe('standardLine', () => {
  it('prefers the standard rung over alternates', () => {
    const lines = [{ line: 0.5, oddsType: 'goblin', fetchedAt: 'x' }, { line: 1.5, oddsType: 'standard', fetchedAt: 'x' }, { line: 2.5, oddsType: 'demon', fetchedAt: 'x' }]
    expect(standardLine(market({ lines }))).toBe(1.5)
  })

  it('is null without a standard rung', () => {
    expect(standardLine(market({ lines: [{ line: 2.5, oddsType: 'demon', fetchedAt: 'x' }] }))).toBeNull()
  })
})

describe('playerTabs', () => {
  it('lists model tabs first, then line-only tabs in board order', () => {
    expect(playerTabs(['passing_yards'], ['punts', 'interceptions', 'passing_touchdowns'])).toEqual([
      { market: 'passing_yards', kind: 'model' }, { market: 'passing_touchdowns', kind: 'other' },
      { market: 'interceptions', kind: 'other' }, { market: 'punts', kind: 'other' },
    ])
  })

  it('gives a kicker only line-only tabs and never lists a market twice', () => {
    expect(playerTabs([], ['kicking_points', 'field_goals_made', 'kicking_points']).map(tab => tab.market)).toEqual(['field_goals_made', 'kicking_points'])
    expect(playerTabs(['interceptions'], ['interceptions']).map(tab => tab.kind)).toEqual(['model'])
  })
})
