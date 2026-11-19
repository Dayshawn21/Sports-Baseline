import { describe, expect, it } from 'vitest'
import { activeDepthLabel, availabilityDepthLabel, depthLabel, injuryLabel, injuryTag, isRoleChanged, roleChangeNote } from './nflAvailability'

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

describe('activeDepthLabel', () => {
  const RB2 = { ...EMPTY, depthPosition: 'RB', depthRank: 2 }

  it('promotes a backup past a teammate ruled out, naming him by surname', () => {
    expect(activeDepthLabel({ ...RB2, activeDepthRank: 1, outAhead: ['Kenneth Walker III'] }))
      .toBe('RB1 (RB2 on chart, Walker out)')
  })

  it('names every teammate out ahead', () => {
    expect(activeDepthLabel({ ...EMPTY, depthPosition: 'RB', depthRank: 4, activeDepthRank: 2, outAhead: ['Kenneth Walker III', 'Jaydn Ott'] }))
      .toBe('RB2 (RB4 on chart, Walker, Ott out)')
  })

  it('keeps an out player at his chart slot and says he is out', () => {
    expect(activeDepthLabel({ ...EMPTY, depthPosition: 'RB', depthRank: 1, activeDepthRank: null, outAhead: [] }))
      .toBe('RB1 on chart, out')
  })

  it('shows the plain chart rank when no one ahead is out', () => {
    expect(activeDepthLabel({ ...EMPTY, depthPosition: 'WR', depthRank: 2, activeDepthRank: 2, outAhead: [] })).toBe('WR2')
  })

  it('treats a slate stored before the field as unchanged', () => {
    expect(activeDepthLabel(RB2)).toBe('RB2')
    expect(availabilityDepthLabel({ ...RB2, previousDepthPosition: 'RB', previousDepthRank: 3 })).toBe('RB2 (was RB3)')
  })

  it('prefers the active label over the week-over-week move when an out changes the depth', () => {
    expect(availabilityDepthLabel({ ...RB2, previousDepthPosition: 'RB', previousDepthRank: 3, activeDepthRank: 1, outAhead: ['Kenneth Walker III'] }))
      .toBe('RB1 (RB2 on chart, Walker out)')
  })

  it('has no label for a player off the chart', () => {
    expect(activeDepthLabel({ ...EMPTY, activeDepthRank: null })).toBeNull()
  })
})

describe('isRoleChanged and roleChangeNote', () => {
  const healthy = { injuryStatus: null, qualityFlags: [], depthPosition: 'RB', depthRank: 2, activeDepthRank: 2, outAhead: [] }

  it('trusts the API flag on its own', () => {
    const row = { ...healthy, qualityFlags: ['role_changed'] }
    expect(isRoleChanged(row)).toBe(true)
    expect(roleChangeNote(row)).toBe('Role changed: a teammate ahead is out')
  })

  it('guards an Out player in a slate stored before the flag', () => {
    const row = { ...healthy, injuryStatus: 'Out', activeDepthRank: null }
    expect(isRoleChanged(row)).toBe(true)
    expect(roleChangeNote(row)).toBe('Player is out')
  })

  it('guards a backup moved up by an Out starter without the flag', () => {
    const row = { ...healthy, activeDepthRank: 1, outAhead: ['Kenneth Walker III'] }
    expect(isRoleChanged(row)).toBe(true)
    expect(roleChangeNote(row)).toBe('Role changed: Walker out')
  })

  it('leaves a healthy line, or one from a slate with no active depth, alone', () => {
    expect(isRoleChanged(healthy)).toBe(false)
    expect(roleChangeNote(healthy)).toBeNull()
    expect(isRoleChanged({ injuryStatus: 'Questionable', qualityFlags: ['injury_questionable'], depthPosition: 'RB', depthRank: 1 })).toBe(false)
  })
})
