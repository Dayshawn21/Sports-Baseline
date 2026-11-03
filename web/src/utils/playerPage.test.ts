import { describe, expect, it } from 'vitest'
import { marketCountLabel } from '~/utils/playerPage'

describe('marketCountLabel', () => {
  it('uses the singular only for one market', () => {
    expect(marketCountLabel(1)).toBe('1 market')
    expect(marketCountLabel(2)).toBe('2 markets')
    expect(marketCountLabel(0)).toBe('0 markets')
  })
})
