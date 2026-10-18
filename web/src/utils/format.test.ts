import { describe, expect, it } from 'vitest'
import { fmtDateCT, fmtStartCT, fmtTimeCT } from '~/utils/format'

// 2026-08-25T18:00:00Z == 1:00 PM America/Chicago (CDT, UTC-5)
const NOW = Date.parse('2026-08-25T18:00:00Z')

describe('Central clock and date labels', () => {
  it.each([
    ['2026-01-15T18:00:00Z', '12:00 PM CT', 'Thu, Jan 15'],
    ['2026-07-15T18:00:00Z', '1:00 PM CT', 'Wed, Jul 15'],
    ['2026-07-01T04:30:00Z', '11:30 PM CT', 'Tue, Jun 30'],
    ['2026-07-01T05:00:00Z', '12:00 AM CT', 'Wed, Jul 1'],
  ])('keeps the Central offset and calendar day for %s', (value, time, date) => {
    expect(fmtTimeCT(value)).toBe(time)
    expect(fmtDateCT(value)).toBe(date)
  })

  it.each([null, undefined, '', 'not a date'])('omits unavailable clock and date labels: %s', value => {
    expect(fmtTimeCT(value)).toBe('')
    expect(fmtDateCT(value)).toBe('')
  })
})

describe('fmtStartCT', () => {
  it('shows time alone for a match later today', () => {
    expect(fmtStartCT('2026-08-25T22:30:00Z', NOW)).toBe('5:30 PM CT')
  })

  it('names tomorrow rather than leaving a bare clock time', () => {
    // The reported confusion: a 10:00 AM card that is actually the 26th.
    expect(fmtStartCT('2026-08-26T15:00:00Z', NOW)).toBe('Tomorrow · 10:00 AM CT')
  })

  // fmtDateCT renders "Thu, Aug 27" — Intl puts a comma after the weekday
  // even though the helper's own docstring omits it.
  it('spells out a date further ahead', () => {
    expect(fmtStartCT('2026-08-27T15:00:00Z', NOW)).toBe('Thu, Aug 27 · 10:00 AM CT')
  })

  it('spells out a past date too', () => {
    expect(fmtStartCT('2026-08-24T15:00:00Z', NOW)).toBe('Mon, Aug 24 · 10:00 AM CT')
  })

  it('compares CT calendar days, not a 24-hour offset', () => {
    // 04:30Z on the 26th is 11:30 PM CT on the 25th — still today, despite
    // being a different UTC day.
    expect(fmtStartCT('2026-08-26T04:30:00Z', NOW)).toBe('11:30 PM CT')
    // 05:30Z is 12:30 AM CT on the 26th — tomorrow, only an hour later.
    expect(fmtStartCT('2026-08-26T05:30:00Z', NOW)).toBe('Tomorrow · 12:30 AM CT')
  })

  it('is empty for a missing or unparseable start', () => {
    expect(fmtStartCT(null, NOW)).toBe('')
    expect(fmtStartCT(undefined, NOW)).toBe('')
    expect(fmtStartCT('not a date', NOW)).toBe('')
  })
})
