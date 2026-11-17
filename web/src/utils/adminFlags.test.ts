import { describe, expect, it } from 'vitest'
import { EMPTY_ELO_INPUTS, buildSetEloPayload, fetchEloPayload, fixStatsPayload, hasEloFlag, hasStatsFlag, surfaceGapNote } from './adminFlags'

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

describe('buildSetEloPayload', () => {
  it('needs a nonzero Overall', () => {
    expect(buildSetEloPayload(EMPTY_ELO_INPUTS)).toBeNull()
    expect(buildSetEloPayload({ ...EMPTY_ELO_INPUTS, elo: '0' })).toBeNull()
    expect(buildSetEloPayload({ ...EMPTY_ELO_INPUTS, elo: 'abc', hard: '1600' })).toBeNull()
  })

  it('sends blank surfaces as null and typed ones as numbers', () => {
    expect(buildSetEloPayload({ elo: '1550', hard: '1600', clay: '', grass: '1480' }))
      .toEqual({ elo: 1550, eloHard: 1600, eloClay: null, eloGrass: 1480 })
  })
})

describe('fixStatsPayload', () => {
  it('sends an empty slug as null', () => {
    expect(fixStatsPayload('')).toEqual({ taSlug: null })
    expect(fixStatsPayload('JannikSinner')).toEqual({ taSlug: 'JannikSinner' })
  })
})

describe('fetchEloPayload', () => {
  it('overrides the name only when it was changed', () => {
    expect(fetchEloPayload('Jannik Sinner', 'Jannik Sinner')).toEqual({ taName: null })
    expect(fetchEloPayload('J. Sinner', 'Jannik Sinner')).toEqual({ taName: 'J. Sinner' })
  })
})

describe('repair flags', () => {
  it('reads which panels a player needs', () => {
    expect(hasEloFlag(['p2_elo_missing'])).toBe(true)
    expect(hasEloFlag(['ml_features_partial', 'high_overround'])).toBe(false)
    expect(hasStatsFlag(['ml_features_partial'])).toBe(true)
    expect(hasStatsFlag(['elo_missing'])).toBe(false)
  })
})
