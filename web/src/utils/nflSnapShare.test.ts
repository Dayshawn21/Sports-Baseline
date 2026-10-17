import { describe, expect, it } from 'vitest'
import { snapShareLabel } from './nflSnapShare'

describe('snapShareLabel', () => {
  it('shows the share as a percent with its game count', () => {
    expect(snapShareLabel({ snapShare: 0.879, snapShareGames: 31 })).toBe('88% · 31 g, season-weighted')
  })

  it('shows the unavailable state, not 0%, when the player has no snap history', () => {
    expect(snapShareLabel({ snapShare: null, snapShareGames: 0 })).toBe('No snap history (position average used)')
  })

  it('keeps a real zero share distinct from no history', () => {
    expect(snapShareLabel({ snapShare: 0, snapShareGames: 3 })).toBe('0% · 3 g, season-weighted')
  })

  it('returns null for lines snap share does not feed', () => {
    expect(snapShareLabel({ snapShare: null, snapShareGames: null })).toBeNull()
  })
})
