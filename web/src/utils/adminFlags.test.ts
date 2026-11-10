import { describe, expect, it } from 'vitest'
import { surfaceGapNote } from './adminFlags'

describe('surfaceGapNote', () => {
  it('stays silent with no surface gap', () => expect(surfaceGapNote([])).toBeNull())

  it('names one missing surface', () => {
    expect(surfaceGapNote(['Clay'])).toBe(
      'No Clay stats. Fix Stats can add them only with 3+ matches on that surface in the last 52 weeks.',
    )
  })

  it('names several missing surfaces', () => {
    expect(surfaceGapNote(['Clay', 'Grass'])).toContain('No Clay or Grass stats.')
  })
})
