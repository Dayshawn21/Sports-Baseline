import { describe, expect, it } from 'vitest'
import type { PlayerEloPoint } from '~/types/tennis'
import { ageOn, chartSurface, defaultSurface, eloChart, metricBar, metricText, parsePlayerId, ratio, recordText, shortDate, dateWithYear } from '~/utils/tennisPlayer'

const NOW = new Date('2026-09-29T12:00:00Z')
const BOX = { left: 40, right: 600, top: 20, bottom: 160 }

function point(asOf: string, overall: number | null, hard: number | null = null): PlayerEloPoint {
  return { asOf, overall, hard, clay: null, grass: null }
}

describe('parsePlayerId', () => {
  it('accepts positive integers only', () => {
    expect(parsePlayerId('26')).toBe(26)
    expect(parsePlayerId('abc')).toBeNull()
    expect(parsePlayerId('0')).toBeNull()
    expect(parsePlayerId(undefined)).toBeNull()
  })
})

describe('ageOn', () => {
  it('counts whole years and waits for the birthday', () => {
    expect(ageOn('2005-09-30', NOW)).toBe(20)
    expect(ageOn('2005-09-29', NOW)).toBe(21)
    expect(ageOn('2001-11-05', NOW)).toBe(24)
  })

  it('is null without a birth date', () => {
    expect(ageOn(null, NOW)).toBeNull()
    expect(ageOn('not a date', NOW)).toBeNull()
  })
})

describe('recordText', () => {
  it('shows wins, losses and the win share', () => {
    expect(recordText({ wins: 39, losses: 21 })).toBe('39-21 · 65%')
  })

  it('shows a dash with no matches', () => {
    expect(recordText({ wins: 0, losses: 0 })).toBe('—')
  })
})

describe('metricBar and metricText', () => {
  it('scales percentages to 1 and serve-point rates to their own ceiling', () => {
    expect(metricBar(0.84, 'holdPct')).toBeCloseTo(84)
    expect(metricBar(0.144, 'acesPerGame')).toBeCloseTo(57.6)
    expect(metricBar(0.049, 'dfPerGame')).toBeCloseTo(49)
  })

  it('clamps a value above its scale and passes a missing one through', () => {
    expect(metricBar(0.4, 'acesPerGame')).toBe(100)
    expect(metricBar(null, 'holdPct')).toBeNull()
  })

  it('formats rates with a decimal and percentages whole', () => {
    expect(metricText(0.84, 'holdPct')).toBe('84%')
    expect(metricText(0.144, 'acesPerGame')).toBe('14.4%')
    expect(metricText(null, 'dfPerGame')).toBe('—')
  })
})

describe('surface choices', () => {
  it('opens on the next match surface, else all, and charts hard by default', () => {
    expect(defaultSurface('Clay')).toBe('Clay')
    expect(defaultSurface(null)).toBe('all')
    expect(chartSurface('Grass')).toBe('grass')
    expect(chartSurface(undefined)).toBe('hard')
  })
})

describe('eloChart', () => {
  const history = [point('2026-01-05', 1864.1, 1839.1), point('2026-05-04', 1890, null), point('2026-08-24', 1910.4, 1874.9)]

  it('places points by date and rating inside the box', () => {
    const chart = eloChart(history, ['overall', 'hard'], BOX)!

    expect(chart.series.overall).toHaveLength(3)
    expect(chart.series.hard).toHaveLength(2)
    expect(chart.series.overall[0].x).toBe(BOX.left)
    expect(chart.series.overall[2].x).toBe(BOX.right)
    for (const p of chart.series.overall) {
      expect(p.y).toBeGreaterThanOrEqual(BOX.top)
      expect(p.y).toBeLessThanOrEqual(BOX.bottom)
    }
    expect(chart.series.overall[2].y).toBeLessThan(chart.series.overall[0].y)
  })

  it('rounds the y ticks outward and labels the first and last dates', () => {
    const chart = eloChart(history, ['overall', 'hard'], BOX)!

    expect(chart.ticks.map((t) => t.value)).toEqual([1930, 1875, 1820])
    expect(chart.dates.map((d) => d.label)).toEqual(["Jan '26", "Aug '26"])
  })

  it('centers a single snapshot and returns null with no ratings', () => {
    const single = eloChart([point('2026-01-05', 1864.1)], ['overall'], BOX)!

    expect(single.series.overall).toEqual([{ x: 320, y: expect.any(Number) }])
    expect(single.dates).toHaveLength(1)
    expect(eloChart([], ['overall'], BOX)).toBeNull()
    expect(eloChart([point('2026-01-05', null)], ['overall'], BOX)).toBeNull()
  })
})

describe('shortDate and ratio', () => {
  it('formats a plain date without shifting it a day', () => {
    expect(shortDate('2026-09-25')).toBe('Sep 25')
    expect(shortDate('2026-01-01')).toBe('Jan 1')
    expect(shortDate('garbage')).toBe('garbage')
    expect(dateWithYear('2025-09-29')).toBe('Sep 29, 2025')
  })

  it('shows made over chances, or a dash when either is missing', () => {
    expect(ratio(3, 4)).toBe('3/4')
    expect(ratio(0, 0)).toBe('0/0')
    expect(ratio(null, 4)).toBe('—')
  })
})
