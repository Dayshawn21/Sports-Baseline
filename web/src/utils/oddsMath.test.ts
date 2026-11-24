import { describe, expect, it } from 'vitest'
import fixture from '../../../api/tests/fixtures/calculator_cases.json'
import { americanToProb } from '~/utils/odds'
import {
  americanToDecimal,
  breakEvenProbability,
  decimalToAmerican,
  expectedValue,
  impliedProbFromAmerican,
  kellyFraction,
  overround,
  probToAmerican,
  roundHalfEven,
} from '~/utils/oddsMath'

interface KellyArgs { prob: number, odds_american: number, max_fraction?: number, multiplier?: number }

interface Fixture {
  [name: string]: { in: number[], out: number | number[] }[] | { in: KellyArgs, out: number }[]
  kelly_fraction: { in: KellyArgs, out: number }[]
}

// The JSON's inferred type is a literal union per key; one cast states the shape both suites rely on.
const FIXTURE = fixture as unknown as Fixture

type Positional = (...args: number[]) => number | [number, number]

/** The same cases `api/tests/test_calculator_cases.py` holds `app/core` to. */
const POSITIONAL: Record<string, Positional> = {
  american_to_prob: americanToProb,
  american_to_decimal: americanToDecimal,
  decimal_to_american: decimalToAmerican,
  prob_to_american: probToAmerican,
  break_even_probability: breakEvenProbability,
  implied_prob_from_american: (a, b) => impliedProbFromAmerican(a, b),
  overround: (a, b) => overround(a, b),
  expected_value: (p, odds) => expectedValue(p, odds),
}

const INTEGER_RESULTS = new Set(['decimal_to_american', 'prob_to_american'])

function expectClose(actual: number, expected: number) {
  expect(actual).toBeCloseTo(expected, 9)
}

describe('oddsMath against the shared fixture', () => {
  for (const [name, fn] of Object.entries(POSITIONAL)) {
    const cases = FIXTURE[name] as { in: number[], out: number | number[] }[]

    it(`${name} has cases`, () => expect(cases.length).toBeGreaterThan(0))

    for (const { in: args, out } of cases) {
      it(`${name}(${args.join(', ')})`, () => {
        const result = fn(...args)
        if (Array.isArray(out)) {
          expect(Array.isArray(result)).toBe(true)
          out.forEach((value, index) => expectClose((result as number[])[index], value))
        } else if (INTEGER_RESULTS.has(name)) {
          expect(result).toBe(out)
        } else {
          expectClose(result as number, out)
        }
      })
    }
  }

  for (const { in: args, out } of FIXTURE.kelly_fraction) {
    it(`kelly_fraction(${JSON.stringify(args)})`, () => {
      expectClose(kellyFraction(args.prob, args.odds_american, args.max_fraction, args.multiplier), out)
    })
  }
})

describe('roundHalfEven', () => {
  it('rounds ties to even as Python does', () => {
    expect([0.5, 1.5, 2.5, 112.5, 113.5, -112.5, -0.5].map(roundHalfEven)).toEqual([0, 2, 2, 112, 114, -112, -0])
  })

  it('rounds non-ties normally', () => {
    expect([112.4, 112.6, -112.6, 113.49999999].map(roundHalfEven)).toEqual([112, 113, -113, 113])
  })
})
