import { describe, expect, it } from 'vitest'
import { heroDelta, mainLine } from '~/utils/playerProjection'

describe('mainLine', () => {
  it('prefers the standard rung, then an untyped one, else the first', () => {
    expect(mainLine([{ oddsType: 'goblin' }, { oddsType: 'standard' }])).toEqual({ oddsType: 'standard' })
    expect(mainLine([{ oddsType: 'demon' }, { oddsType: null }])).toEqual({ oddsType: null })
    expect(mainLine([{ oddsType: 'demon' }])).toEqual({ oddsType: 'demon' })
    expect(mainLine([])).toBeNull()
  })
})

describe('heroDelta', () => {
  it('reads the gap against the line, and nothing without a number or a gap', () => {
    expect(heroDelta('229.8', { line: '237.5', gap: '-7.7', oddsType: 'standard' })).toBe('-7.7 vs 237.5 line')
    expect(heroDelta(null, { line: '237.5', gap: '-7.7', oddsType: 'standard' })).toBeNull()
    expect(heroDelta('229.8', { line: '237.5', gap: null, oddsType: 'standard' })).toBeNull()
    expect(heroDelta('229.8', null)).toBeNull()
    expect(heroDelta('1.4', { line: '0.5', gap: '+0.9', oddsType: 'goblin' })).toBe('+0.9 vs 0.5 goblin line')
  })
})
