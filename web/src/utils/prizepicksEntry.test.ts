import { describe, expect, it } from 'vitest'
import fixture from '../../../api/tests/fixtures/calculator_cases.json'
import { entryEv, hitCountDistribution } from '~/utils/prizepicksEntry'

interface EntryCase {
  in: { probs: number[], kind: string }
  out: { distribution: number[], expected_multiple: number, ev: number }
}

const VALID = fixture.entry_ev as EntryCase[]
const INVALID = fixture.entry_ev_invalid as { in: EntryCase['in'] }[]

describe('entryEv against the shared fixture', () => {
  it('has cases', () => {
    expect(VALID.length).toBeGreaterThan(0)
    expect(INVALID.length).toBeGreaterThan(0)
  })

  for (const { in: input, out } of VALID) {
    it(`${input.kind} [${input.probs.join(', ')}]`, () => {
      const outcome = entryEv(input.probs, input.kind)
      if (!outcome.ok) throw new Error(outcome.reason)
      expect(outcome.result.distribution).toHaveLength(out.distribution.length)
      outcome.result.distribution.forEach((mass, hits) => expect(mass).toBeCloseTo(out.distribution[hits], 9))
      expect(outcome.result.expectedMultiple).toBeCloseTo(out.expected_multiple, 9)
      expect(outcome.result.ev).toBeCloseTo(out.ev, 9)
    })
  }

  for (const { in: input } of INVALID) {
    it(`rejects ${input.kind} [${input.probs.join(', ')}] with a reason`, () => {
      const outcome = entryEv(input.probs, input.kind)
      expect(outcome.ok).toBe(false)
      if (!outcome.ok) expect(outcome.reason.length).toBeGreaterThan(0)
    })
  }
})

describe('hitCountDistribution', () => {
  it('sums to one with one entry per hit count', () => {
    const dist = hitCountDistribution([0.52, 0.58, 0.61, 0.57, 0.66])
    expect(dist).toHaveLength(6)
    expect(dist.reduce((sum, mass) => sum + mass, 0)).toBeCloseTo(1, 12)
  })
})
