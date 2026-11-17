import { describe, expect, it } from 'vitest'
import { devigP1, fmtPct } from '~/utils/odds'

describe('devigP1', () => {
  it('normalizes the two implied probabilities to sum to one', () => {
    // -150 / +130: raw 0.6 and 0.4348
    expect(devigP1(-150, 130)).toBeCloseTo(0.6 / 1.0348, 4)
  })

  it('splits an even pair evenly', () => {
    expect(devigP1(-110, -110)).toBeCloseTo(0.5, 10)
  })

  it('needs both sides', () => {
    expect(devigP1(120, null)).toBeNull()
    expect(devigP1(null, -150)).toBeNull()
  })
})

describe('fmtPct', () => {
  it('shows a probability as a percentage to the given decimals', () => {
    expect(fmtPct(0.654)).toBe('65.4%')
    expect(fmtPct(0.12345, 2)).toBe('12.35%')
    expect(fmtPct(0)).toBe('0.0%')
  })

  it('shows the dash glyph for a missing value', () => {
    expect(fmtPct(null)).toBe('—')
    expect(fmtPct(undefined)).toBe('—')
  })
})
