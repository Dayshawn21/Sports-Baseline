import { describe, expect, it } from 'vitest'
import type { NbaLineOnlyRecent, NbaPropLine } from '~/types/nba'
import { lineOnlyBars } from '~/utils/nflLineOnly'
import { NBA_PROP_MARKETS, nbaPropFlagText, nbaPropGroups, rungLabel, signedGap } from '~/utils/nbaProps'

function recent(...values: Array<number | null>): NbaLineOnlyRecent[] {
  return values.map((value, index) => ({ gameDate: `2026-05-${String(20 - index).padStart(2, '0')}`, opponent: 'NY', value }))
}

function line(overrides: Partial<NbaPropLine>): NbaPropLine {
  return {
    playerId: 1, playerName: 'Cade Cunningham', position: 'G', team: 'DET', market: 'assists',
    oddsType: 'standard', line: 9.5, fetchedAt: '2026-10-06T16:30:00Z', recent: recent(5, 8, 9, 6, 10),
    projection: 8, gamesInSample: 20, priorMinutes: 41.4, gap: -1.5,
    pOver: 0.345, pUnder: 0.655, overProbabilityVersion: 'nba-pover-v1', flags: [], ...overrides,
  }
}

function points(overrides: Partial<NbaPropLine>): NbaPropLine {
  return line({
    market: 'points', line: 24.5, projection: 24.2, gap: -0.3, pOver: null, pUnder: null,
    overProbabilityVersion: null, flags: ['no_over_probability'], ...overrides,
  })
}

describe('nbaPropGroups', () => {
  it('orders markets as NbaPropMarket, then one card per player by name', () => {
    const groups = nbaPropGroups([
      line({ market: 'rebounds_assists', line: 14.5 }),
      line({}),
      points({ playerId: 2, playerName: 'Jayson Tatum', team: 'BOS' }),
      points({}),
    ])
    expect(groups.map(group => group.market)).toEqual(['points', 'assists', 'rebounds_assists'])
    expect(groups[0].cards.map(card => [card.playerName, card.team])).toEqual([['Cade Cunningham', 'DET'], ['Jayson Tatum', 'BOS']])
    expect(NBA_PROP_MARKETS).toHaveLength(9)
    expect(NBA_PROP_MARKETS).not.toContain('double_double')
  })

  it('collapses rungs in line order and leads with the standard rung', () => {
    const [group] = nbaPropGroups([
      line({ line: 11.5, oddsType: 'demon', gap: -3.5, pOver: 0.239, pUnder: 0.761 }),
      line({}),
      line({ line: 7.5, oddsType: 'goblin', gap: 0.5, pOver: 0.486, pUnder: 0.514 }),
    ])
    const [card] = group.cards
    expect(card.rungs.map(rung => rung.line)).toEqual([7.5, 9.5, 11.5])
    expect(card.main.line).toBe(9.5)
    expect(card.also).toEqual(['7.5 goblin · 49%', '11.5 demon · 24%'])
  })

  it('leads with the lowest rung when there is no standard line', () => {
    const [group] = nbaPropGroups([
      line({ line: 9.5, oddsType: 'demon', gap: -1.65, pOver: 0.177, pUnder: 0.823 }),
      line({ line: 7.5, oddsType: 'demon', gap: 0.35, pOver: 0.3, pUnder: 0.7 }),
    ])
    const [card] = group.cards
    expect(card.main.line).toBe(7.5)
    expect(card.projectionRow?.gap).toBe('+0.4')
    expect(card.also).toEqual(['9.5 demon · 18%'])
    expect(card.overCount).toBeNull()
  })

  it('prints the projection row with P(over) when the market has a fit', () => {
    const [card] = nbaPropGroups([line({})])[0].cards
    expect(card.projectionRow).toEqual({ projection: '8.0', gap: '-1.5', pOver: '35%', pUnder: '66%' })
    expect(card).toMatchObject({ gamesInSample: 20, priorMinutes: 41.4 })
    expect(card.flagText).toBeNull()
  })

  it('prints the projection row without P(over), saying why', () => {
    const [card] = nbaPropGroups([points({})])[0].cards
    expect(card.projectionRow).toEqual({ projection: '24.2', gap: '-0.3', pOver: null, pUnder: null })
    expect(card.flagText).toBe('P(over) not fitted for this market')
  })

  it('an Also rung without P(over) prints the line alone', () => {
    const [card] = nbaPropGroups([points({}), points({ line: 29.5, oddsType: 'demon', gap: -5.3 })])[0].cards
    expect(card.also).toEqual(['29.5 demon'])
  })

  it('gives an ineligible player no projection row and the reason', () => {
    const ineligible = { projection: null, gap: null, pOver: null, pUnder: null, overProbabilityVersion: null }
    const [few] = nbaPropGroups([line({ ...ineligible, flags: ['few_prior_games'] })])[0].cards
    const [low] = nbaPropGroups([line({ ...ineligible, flags: ['low_minutes'] })])[0].cards
    expect(few.projectionRow).toBeNull()
    expect(few.flagText).toBe('No projection: fewer than 10 earlier games')
    expect(low.flagText).toBe('No projection: under 20 minutes a game')
  })

  it('a whole-number main line keeps its projection but has no P(over)', () => {
    const [card] = nbaPropGroups([line({ line: 3, projection: 2.85, gap: -0.15, pOver: null, pUnder: null, flags: ['integer_line'] })])[0].cards
    expect(card.projectionRow).toEqual({ projection: '2.9', gap: '-0.1', pOver: null, pUnder: null })
    expect(card.flagText).toBe('Whole-number line: no P(over)')
  })

  it('counts recent games over the standard line, and the bars read the card', () => {
    const [card] = nbaPropGroups([line({})])[0].cards
    expect([card.overCount, card.count]).toEqual([1, 5])
    expect(lineOnlyBars(card).bars.map(bar => bar.value)).toEqual([10, 6, 9, 8, 5])
  })
})

describe('signedGap', () => {
  it('signs positives, keeps negatives, rounds to one place', () => {
    expect(signedGap(1.94)).toBe('+1.9')
    expect(signedGap(1.96)).toBe('+2.0')
    expect(signedGap(-3.85)).toBe('-3.8')
    expect(signedGap(-0.04)).toBe('0.0')
    expect(signedGap(0.04)).toBe('0.0')
    expect(signedGap(0)).toBe('0.0')
  })
})

describe('rungLabel', () => {
  it('names non-standard rungs and appends P(over)', () => {
    expect(rungLabel({ line: 9.5, oddsType: 'demon', pOver: 0.31 })).toBe('9.5 demon · 31%')
    expect(rungLabel({ line: 9.5, oddsType: 'standard', pOver: null })).toBe('9.5')
  })
})

describe('nbaPropFlagText', () => {
  it('turns each projection flag into drawer-ready text', () => {
    expect(nbaPropFlagText('few_prior_games')).toBe('No projection: fewer than 10 earlier games')
    expect(nbaPropFlagText('integer_line')).toBe('Whole-number line: no P(over)')
  })
})
