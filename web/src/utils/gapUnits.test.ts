import { describe, expect, it } from 'vitest'
import { gapShareOfLine, signedGapUnits } from '~/utils/gapUnits'

describe('signedGapUnits', () => {
  it('signs model minus line to one decimal, with the unit when there is one', () => {
    expect(signedGapUnits(32.62, 'yds')).toBe('+32.6 yds')
    expect(signedGapUnits(-1.05, 'pts')).toBe('-1.1 pts')
    expect(signedGapUnits(-1.5)).toBe('-1.5')
    expect(signedGapUnits(0, 'pts')).toBe('0.0 pts')
  })

  it('shows a dash with no gap', () => {
    expect(signedGapUnits(null, 'yds')).toBe('--')
    expect(signedGapUnits(Number.NaN)).toBe('--')
  })
})

describe('gapShareOfLine', () => {
  it('sizes the gap against the line without a sign', () => {
    expect(gapShareOfLine(-0.143)).toBe('14% of the line')
    expect(gapShareOfLine(null)).toBeNull()
  })
})
