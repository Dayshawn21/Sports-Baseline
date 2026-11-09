import { describe, expect, it } from 'vitest'
import { slatePropsText } from '~/utils/slateProps'

describe('slatePropsText', () => {
  it('shows a dash pair for no props and the count otherwise', () => {
    expect(slatePropsText(0)).toBe('--')
    expect(slatePropsText(1)).toBe('1')
    expect(slatePropsText(42)).toBe('42')
  })
})
