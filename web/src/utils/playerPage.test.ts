import { describe, expect, it } from 'vitest'
import { injuryTone, latestTime, marketCountLabel } from '~/utils/playerPage'

describe('marketCountLabel', () => {
  it('uses the singular only for one market', () => {
    expect(marketCountLabel(1)).toBe('1 market')
    expect(marketCountLabel(2)).toBe('2 markets')
    expect(marketCountLabel(0)).toBe('0 markets')
  })
})
describe('injuryTone', () => {
  it('is plain with no designation', () => {
    expect(injuryTone(null)).toBe('default')
    expect(injuryTone(' ')).toBe('default')
  })

  it('marks Out strongest, in any case', () => {
    expect(injuryTone('Out')).toBe('out')
    expect(injuryTone(' OUT ')).toBe('out')
  })

  it('treats every other designation as a caution', () => {
    expect(injuryTone('Questionable')).toBe('caution')
    expect(injuryTone('Day-To-Day')).toBe('caution')
  })
})

describe('latestTime', () => {
  it('returns the newest parseable timestamp', () => {
    expect(latestTime(['2026-11-09T17:00:00Z', null, '2026-11-09T23:31:00Z', 'not a time', '2026-11-08T12:00:00Z'])).toBe('2026-11-09T23:31:00Z')
  })

  it('is null when nothing parses', () => {
    expect(latestTime([])).toBeNull()
    expect(latestTime([null, 'bad'])).toBeNull()
  })
})
