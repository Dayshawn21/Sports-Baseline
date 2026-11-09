import { describe, expect, it } from 'vitest'
import { slateRemainingLine } from '~/utils/slateHeadline'
import { dayClockCt } from '~/utils/slatePeriod'

// Monday 2026-11-09, 8:20 AM CT.
const NOW = Date.parse('2026-11-09T14:20:00Z')
const MNF = '2026-11-10T01:15:00Z'

describe('slateRemainingLine', () => {
  it('names the one game left and its start, with no "next"', () => {
    expect(slateRemainingLine([
      { state: 'final', startUtc: '2026-11-08T18:00:00Z' },
      { state: 'pending', startUtc: '2026-11-09T01:20:00Z' },
      { state: 'upcoming', startUtc: MNF },
    ], NOW)).toBe('1 game left · Mon 7:15 PM CT')
  })

  it('counts live games as left and points at the next start', () => {
    expect(slateRemainingLine([
      { state: 'live', startUtc: '2026-11-09T13:00:00Z' },
      { state: 'upcoming', startUtc: MNF },
      { state: 'upcoming', startUtc: '2026-11-10T03:00:00Z' },
    ], NOW)).toBe('3 games left · 1 live · next Mon 7:15 PM CT')
  })

  it('reads NBA and NHL "started" as live', () => {
    expect(slateRemainingLine([{ state: 'started', startUtc: '2026-11-09T13:00:00Z' }], NOW)).toBe('1 game left · 1 live')
  })

  it('says every game is played, and how many results are still pending', () => {
    expect(slateRemainingLine([{ state: 'final', startUtc: null }, { state: 'pending', startUtc: '2026-11-09T01:20:00Z' }], NOW))
      .toBe('All games played · 1 result pending')
    expect(slateRemainingLine([{ state: 'final', startUtc: null }, { state: 'off', startUtc: null }], NOW)).toBe('All games played')
  })

  it('gives an upcoming week its count and first start', () => {
    expect(slateRemainingLine([
      { state: 'upcoming', startUtc: '2026-11-14T01:15:00Z' },
      { state: 'upcoming', startUtc: '2026-11-15T18:00:00Z' },
    ], NOW)).toBe('2 games left · next Fri 7:15 PM CT')
  })

  it('is empty for an empty slate', () => {
    expect(slateRemainingLine([], NOW)).toBe('')
  })
})

describe('dayClockCt', () => {
  it('writes a Central weekday and clock', () => {
    expect(dayClockCt(Date.parse(MNF))).toBe('Mon 7:15 PM CT')
  })
})
