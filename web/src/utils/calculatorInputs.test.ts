import { describe, expect, it } from 'vitest'
import { parseAmerican, parseDecimal, parsePercent, parsePositive, type Parsed } from '~/utils/calculatorInputs'

function value(parsed: Parsed<number>): number | undefined {
  return parsed.state === 'ok' ? parsed.value : undefined
}

describe('parseAmerican', () => {
  it('accepts whole odds at or beyond 100 either way', () => {
    expect(['+150', '150', '-110', ' -100 ', '+100'].map(text => value(parseAmerican(text)))).toEqual([150, 150, -110, -100, 100])
  })

  it('rejects odds inside (-100, 100) and fractions', () => {
    for (const text of ['99', '-99', '0', '-110.5']) expect(parseAmerican(text).state).toBe('invalid')
  })

  it('rejects text that is not a number', () => {
    for (const text of ['abc', '1e3', '+', '--110']) expect(parseAmerican(text)).toEqual({ state: 'invalid', reason: 'Enter a number.' })
  })

  it('treats an empty or blank field as quiet', () => {
    expect(parseAmerican('')).toEqual({ state: 'empty' })
    expect(parseAmerican('   ')).toEqual({ state: 'empty' })
  })
})

describe('parseDecimal', () => {
  it('accepts prices above 1', () => {
    expect(['1.91', '2', '.5e'].map(text => parseDecimal(text).state)).toEqual(['ok', 'ok', 'invalid'])
    expect(value(parseDecimal('3.50'))).toBe(3.5)
  })

  it('rejects 1 and below', () => {
    for (const text of ['1.0', '1', '0.8', '-2']) expect(parseDecimal(text).state).toBe('invalid')
  })
})

describe('parsePercent', () => {
  it('returns a 0-1 probability, with or without a percent sign', () => {
    expect(value(parsePercent('55'))).toBeCloseTo(0.55, 12)
    expect(value(parsePercent('52.4%'))).toBeCloseTo(0.524, 12)
  })

  it('rejects 0, 100 and beyond', () => {
    for (const text of ['0', '100', '101', '-5']) expect(parsePercent(text).state).toBe('invalid')
  })

  it('keeps an empty field quiet', () => {
    expect(parsePercent('')).toEqual({ state: 'empty' })
  })
})

describe('parsePositive', () => {
  it('accepts amounts above zero', () => {
    expect(value(parsePositive('1000'))).toBe(1000)
    expect(value(parsePositive('12.50'))).toBe(12.5)
  })

  it('rejects zero and negatives', () => {
    for (const text of ['0', '-10']) expect(parsePositive(text).state).toBe('invalid')
  })
})
