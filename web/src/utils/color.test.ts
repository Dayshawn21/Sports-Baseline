import { describe, expect, it } from 'vitest'
import { withAlpha } from '~/utils/color'

describe('withAlpha', () => {
  it('tints a theme token, which a hex alpha suffix would turn into invalid CSS', () => {
    expect(withAlpha('var(--positive)', 0.25)).toBe('color-mix(in srgb, var(--positive) 25%, transparent)')
  })

  it('tints a plain hex color the same way', () => {
    expect(withAlpha('#3b82f6', 0.08)).toBe('color-mix(in srgb, #3b82f6 8%, transparent)')
  })

  it('rounds to a whole percent', () => {
    expect(withAlpha('red', 0.2083)).toBe('color-mix(in srgb, red 21%, transparent)')
  })

  it('clamps alpha to the 0-1 range', () => {
    expect(withAlpha('red', 1.4)).toBe('color-mix(in srgb, red 100%, transparent)')
    expect(withAlpha('red', -0.2)).toBe('color-mix(in srgb, red 0%, transparent)')
  })
})
