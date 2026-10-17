import { describe, expect, it } from 'vitest'
import { depthLabel, injuryLabel, injuryTag } from './nflAvailability'

const EMPTY = {
  injuryStatus: null, practiceStatus: null, injury: null,
  depthPosition: null, depthRank: null, previousDepthPosition: null, previousDepthRank: null,
}

describe('injuryTag', () => {
  it('abbreviates each game status', () => {
    expect(injuryTag('Out')).toEqual({ label: 'OUT', color: 'red' })
    expect(injuryTag('Doubtful')?.label).toBe('D')
    expect(injuryTag('Questionable')?.label).toBe('Q')
  })

  it('shows no tag without a game status', () => {
    expect(injuryTag(null)).toBeNull()
    expect(injuryTag('Probable')).toBeNull()
  })
})

describe('injuryLabel', () => {
  it('joins status, injury, and practice participation', () => {
    expect(injuryLabel({ ...EMPTY, injuryStatus: 'Questionable', injury: 'Hamstring', practiceStatus: 'Limited Participation in Practice' }))
      .toBe('Questionable · Hamstring · limited practice')
  })

  it('names a practice-only listing rather than implying a game status', () => {
    expect(injuryLabel({ ...EMPTY, injury: 'Knee', practiceStatus: 'Full Participation in Practice' }))
      .toBe('Practice report only · Knee · full practice')
  })

  it('is null when the player is not on the report', () => {
    expect(injuryLabel(EMPTY)).toBeNull()
  })
})

describe('depthLabel', () => {
  it('shows the move against the previous chart', () => {
    expect(depthLabel({ ...EMPTY, depthPosition: 'TE', depthRank: 1, previousDepthPosition: 'TE', previousDepthRank: 2 }))
      .toBe('TE1 (was TE2)')
  })

  it('shows just the slot when unchanged', () => {
    expect(depthLabel({ ...EMPTY, depthPosition: 'WR', depthRank: 2, previousDepthPosition: 'WR', previousDepthRank: 2 }))
      .toBe('WR2')
  })

  it('marks a first listing and is null when not listed', () => {
    expect(depthLabel({ ...EMPTY, depthPosition: 'RB', depthRank: 3 })).toBe('RB3 (first listing)')
    expect(depthLabel(EMPTY)).toBeNull()
  })
})

describe('game-notes entries', () => {
  it('label an injury and a depth move without slate-line fields', () => {
    const injury = { injuryStatus: 'Out', practiceStatus: 'Did Not Participate In Practice', injury: 'Neck' }
    const depth = { depthPosition: 'RB', depthRank: 1, previousDepthPosition: 'RB', previousDepthRank: 2 }

    expect(injuryLabel(injury)).toBe('Out · Neck · did not practice')
    expect(depthLabel(depth)).toBe('RB1 (was RB2)')
  })
})
