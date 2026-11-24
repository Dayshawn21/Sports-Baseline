import { describe, expect, it } from 'vitest'
import type { PropReasonRecentValue } from '~/types/tennis'
import { hasReasons, reasonsChartSample } from '~/utils/tennisPropReasons'

function recent(matchDate: string, value: number): PropReasonRecentValue {
  return { matchDate, opponentName: 'Iga Swiatek', surface: 'Hard', bestOf: 3, value }
}

describe('hasReasons', () => {
  it('opens for a stored PrizePicks line with a number', () => {
    expect(hasReasons({ id: 336871, source: 'prizepicks', line: '4.5' })).toBe(true)
  })

  it('stays closed for DraftKings, browser-built and number-less rows', () => {
    expect(hasReasons({ id: 12, source: 'draftkings', line: '20.5' })).toBe(false)
    expect(hasReasons({ id: -21, source: 'market', line: '-150' })).toBe(false)
    expect(hasReasons({ id: -103, source: 'model', line: null })).toBe(false)
    expect(hasReasons({ id: 336871, source: 'prizepicks', line: null })).toBe(false)
  })
})

describe('reasonsChartSample', () => {
  it('turns the oldest-first values into the newest-first chart sample', () => {
    const sample = reasonsChartSample([recent('2026-10-20', 6), recent('2026-10-27', 9)], 7.5)
    expect(sample.values.map(item => [item.gameDate, item.value])).toEqual([['2026-10-27', 9], ['2026-10-20', 6]])
    expect(sample.average).toBe(7.5)
  })

  it('keeps a value on the line', () => {
    expect(reasonsChartSample([recent('2026-10-20', 7)], 7).values).toHaveLength(1)
  })

  it('has no average for an empty history', () => {
    expect(reasonsChartSample([], 7.5)).toEqual({ average: null, values: [] })
  })
})
