import { describe, expect, it } from 'vitest'
import { slateMatchup } from '~/utils/slateMatchup'

describe('slateMatchup', () => {
  it('writes away @ home, with each score beside its team once both are in', () => {
    expect(slateMatchup({ code: 'JAX', score: null }, { code: 'BAL', score: null })).toBe('JAX @ BAL')
    expect(slateMatchup({ code: 'JAX', score: 33 }, { code: 'BAL', score: null })).toBe('JAX @ BAL')
    expect(slateMatchup({ code: 'JAX', score: 33 }, { code: 'BAL', score: 10 })).toBe('JAX 33 @ BAL 10')
  })
})
