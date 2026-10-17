import { describe, expect, it } from 'vitest'
import type { NflBestLine, NflBestSide } from '~/types/nfl'
import { ageLabel, bookLabel, fairLabel, nflBestLineRows, sideLabel, vsFairLabel } from './nflBestLine'

const NOW = new Date('2026-10-07T17:00:00Z')

const side = (overrides: Partial<NflBestSide>): NflBestSide => ({
  side: 'home', line: null, odds: -110, book: 'draftkings', provider: 'odds_api_io',
  fetchedAt: '2026-10-07T15:41:00Z', evPct: null, pointsVsFair: null, ...overrides,
})

const TB_AT_DAL: NflBestLine = {
  maxAgeHours: 36,
  markets: [
    {
      market: 'spread',
      fair: { source: 'pinnacle', line: -8, firstProbability: 0.492, fetchedAt: '2026-10-07T15:50:00Z' },
      sides: [
        side({ side: 'home', line: -8.5, odds: -116, pointsVsFair: -0.5 }),
        side({ side: 'away', line: -9.5, odds: -114, book: 'bet365', pointsVsFair: 1.5 }),
      ],
    },
    {
      market: 'moneyline',
      fair: { source: 'consensus', line: null, firstProbability: 0.787, fetchedAt: '2026-10-07T15:41:00Z' },
      sides: [side({ odds: -476, evPct: -0.0474 }), side({ side: 'away', odds: 370, book: 'bet365', evPct: 0.0012 })],
    },
    { market: 'total', fair: null, sides: [side({ side: 'over', line: 47.5, odds: -111, book: 'bet365' }), side({ side: 'under', line: 47.5, odds: -105 })] },
  ],
}

describe('nflBestLineRows', () => {
  it('reads each side as a bettor would, with book, age and its gap to fair', () => {
    const [spread, moneyline, total] = nflBestLineRows(TB_AT_DAL, 'DAL', 'TB', NOW)

    expect(spread.sides).toEqual([
      { label: 'DAL -8.5', price: '-116', book: 'DraftKings', age: '1h ago', vsFair: '-0.5 pts vs fair' },
      { label: 'TB +9.5', price: '-114', book: 'Bet365', age: '1h ago', vsFair: '+1.5 pts vs fair' },
    ])
    expect(spread.fair).toEqual({ label: 'DAL -8.0', source: 'Pinnacle', age: '1h ago' })
    expect(moneyline.sides.map(row => [row.label, row.price, row.vsFair])).toEqual([['DAL', '-476', '-4.7% vs fair'], ['TB', '+370', '+0.1% vs fair']])
    expect(moneyline.fair).toEqual({ label: 'DAL 78.7%', source: 'Consensus', age: '1h ago' })
    expect(total.fair).toBeNull()
    expect(total.sides.map(row => [row.label, row.vsFair])).toEqual([['O 47.5', null], ['U 47.5', null]])
  })
})

describe('labels', () => {
  it('names known books and title-cases the rest', () => {
    expect([bookLabel('bet365'), bookLabel('bet365', true), bookLabel('draftkings', true), bookLabel('caesars')]).toEqual(['Bet365', 'B365', 'DK', 'Caesars'])
  })

  it('gives ages in minutes, hours, then days, and never a negative age', () => {
    expect(['2026-10-07T16:48:00Z', '2026-10-06T12:00:00Z', '2026-10-04T12:00:00Z', '2026-10-07T17:05:00Z'].map(at => ageLabel(at, NOW)))
      .toEqual(['12m ago', '29h ago', '3d ago', '0m ago'])
  })

  it('reads a pick-em and an away favorite', () => {
    expect(sideLabel(side({ line: 0 }), 'DAL', 'TB')).toBe('DAL PK')
    expect(fairLabel('spread', { source: 'pinnacle', line: 3, firstProbability: 0.5, fetchedAt: '' }, 'DAL', 'TB')).toBe('TB -3.0')
  })

  it('says nothing about fair when there is none, and drops the sign at fair', () => {
    expect(vsFairLabel(side({}))).toBeNull()
    expect([vsFairLabel(side({ evPct: -0.0001 })), vsFairLabel(side({ evPct: 0.0004 }))]).toEqual(['0.0% vs fair', '0.0% vs fair'])
  })
})
