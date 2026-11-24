import { describe, expect, it } from 'vitest'
import fixture from '../../../api/tests/fixtures/calculator_cases.json'
import { betEv, convertOdds, entryView, fmtDecimalOdds, fmtSignedAmount, fmtSignedPct, kellyStake, noVig } from '~/utils/calculators'

function ok<T>(parsed: { state: string, value?: T }): T {
  if (parsed.state !== 'ok') throw new Error(`expected ok, got ${parsed.state}`)
  return parsed.value as T
}

describe('convertOdds', () => {
  it('converts American odds', () => {
    const value = ok(convertOdds('american', '-110'))
    expect(value.american).toBe(-110)
    expect(value.decimal).toBeCloseTo(1.909091, 6)
    expect(value.probability).toBeCloseTo(0.523810, 6)
  })

  it('converts decimal odds with Python rounding', () => {
    expect(ok(convertOdds('decimal', '2.125')).american).toBe(112)
    expect(ok(convertOdds('decimal', '2.5')).probability).toBeCloseTo(0.4, 12)
  })

  it('converts a probability', () => {
    const value = ok(convertOdds('probability', '40'))
    expect(value.american).toBe(150)
    expect(value.decimal).toBeCloseTo(2.5, 12)
  })

  it('passes empty and invalid input through', () => {
    expect(convertOdds('american', '').state).toBe('empty')
    expect(convertOdds('decimal', '0.9').state).toBe('invalid')
  })
})

describe('noVig', () => {
  it('splits an even market', () => {
    const value = ok(noVig('-110', '-110'))
    expect(value.fairA).toBeCloseTo(0.5, 12)
    expect([value.americanA, value.americanB]).toEqual([-100, -100])
    expect(value.overround).toBeCloseTo(0.047619, 6)
  })

  it('devigs an uneven market', () => {
    const value = ok(noVig('-150', '+130'))
    expect(value.fairA).toBeCloseTo(0.579832, 6)
    expect(value.fairA + value.fairB).toBeCloseTo(1, 12)
  })

  it('names the invalid side, and stays quiet while a side is empty', () => {
    expect(noVig('-110', '50')).toMatchObject({ state: 'invalid', reason: expect.stringMatching(/^Side B: /) })
    expect(noVig('-110', '')).toEqual({ state: 'empty' })
  })
})

describe('betEv', () => {
  it('returns EV, break-even and no amount without a stake', () => {
    const value = ok(betEv('55', '-110', ''))
    expect(value.ev).toBeCloseTo(0.05, 12)
    expect(value.breakEven).toBeCloseTo(0.523810, 6)
    expect(value.evAmount).toBeNull()
  })

  it('scales EV by the stake', () => {
    expect(ok(betEv('40', '+200', '50')).evAmount).toBeCloseTo(10, 12)
  })

  it('reports an invalid stake even before the other fields are filled', () => {
    expect(betEv('', '', '-5')).toMatchObject({ state: 'invalid', reason: expect.stringMatching(/^Stake: /) })
  })
})

describe('kellyStake', () => {
  it('sizes Quarter Kelly and scales it by the bankroll', () => {
    const value = ok(kellyStake('55', '-110', 0.25, '1000'))
    expect(value.fraction).toBeCloseTo(0.01375, 12)
    expect(value.stake).toBeCloseTo(13.75, 9)
    expect(value.capped).toBe(false)
  })

  it('flags the 25% cap when it binds', () => {
    const value = ok(kellyStake('70', '+150', 1, ''))
    expect(value.fraction).toBe(0.25)
    expect(value.capped).toBe(true)
    expect(value.stake).toBeNull()
  })

  it('returns no bet on a negative edge', () => {
    expect(ok(kellyStake('45', '-110', 0.25, '')).fraction).toBe(0)
  })

  it('reports an invalid bankroll', () => {
    expect(kellyStake('55', '-110', 0.25, '0')).toMatchObject({ state: 'invalid', reason: expect.stringMatching(/^Bankroll: /) })
  })
})

describe('entryView', () => {
  it('matches the fixture for a 6-leg flex at 60%', () => {
    const expected = fixture.entry_ev.find(entry => entry.in.kind === 'flex' && entry.in.probs.length === 6 && entry.in.probs[0] === 0.6)
    const value = ok(entryView('flex', ['60', '60', '60', '60', '60', '60']))
    expect(value.ev).toBeCloseTo(expected!.out.ev, 9)
  })

  it('lists hit counts from most to fewest with their payouts', () => {
    const value = ok(entryView('flex', ['60', '60', '60']))
    expect(value.rows.map(row => [row.hits, row.multiple])).toEqual([[3, 3], [2, 1], [1, null], [0, null]])
    expect(value.rows[0].probability).toBeCloseTo(0.216, 12)
  })

  it('names the invalid leg and stays quiet while a leg is empty', () => {
    expect(entryView('power', ['60', '120'])).toMatchObject({ state: 'invalid', reason: expect.stringMatching(/^Leg 2: /) })
    expect(entryView('power', ['60', ''])).toEqual({ state: 'empty' })
  })

  it('passes the entry rules through', () => {
    expect(entryView('flex', ['60', '60'])).toEqual({ state: 'invalid', reason: 'Flex needs at least 3 legs.' })
  })
})

describe('formatters', () => {
  it('signs percents and drops the sign at zero', () => {
    expect([0.05, -0.023, 5.55e-17, -1e-6].map(value => fmtSignedPct(value))).toEqual(['+5.0%', '-2.3%', '0.0%', '0.0%'])
  })

  it('trims decimal odds to two or three places', () => {
    expect([1.9090909, 2, 3.5, 2.125].map(fmtDecimalOdds)).toEqual(['1.909', '2.00', '3.50', '2.125'])
  })

  it('signs amounts', () => {
    expect([5, -2.3, 0].map(fmtSignedAmount)).toEqual(['+5.00', '-2.30', '0.00'])
  })
})
