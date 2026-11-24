import { describe, expect, it } from 'vitest'
import { CENTRAL_TZ, ctDayKey, dateWithYear, fmtDateCT, fmtSigned, fmtStartCT, fmtTimeCT, shortDate, tourColor } from '~/utils/format'

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

describe('fmtSigned', () => {
  it('signs positive and negative values', () => {
    expect(fmtSigned(1.25)).toBe('+1.3')
    expect(fmtSigned(-1.25)).toBe('-1.3')
    expect(fmtSigned(32.6, 1, ' yds')).toBe('+32.6 yds')
  })

  it('rounds before signing, so a value that rounds to zero carries no sign', () => {
    expect(fmtSigned(0)).toBe('0.0')
    expect(fmtSigned(-0)).toBe('0.0')
    expect(fmtSigned(0.04)).toBe('0.0')
    expect(fmtSigned(-0.04)).toBe('0.0')
    expect(fmtSigned(-0.0004, 3, '%')).toBe('0.000%')
  })

  it('takes the decimals and suffix', () => {
    expect(fmtSigned(0.123456, 4)).toBe('+0.1235')
    expect(fmtSigned(-12.7, 0)).toBe('-13')
    expect(fmtSigned(5, 1, '%')).toBe('+5.0%')
  })

  it('does not invent a sign for a non-finite value', () => {
    expect(fmtSigned(Number.NaN)).toBe('NaN')
  })
})

describe('plain dates', () => {
  it('formats a YYYY-MM-DD date without shifting it a day', () => {
    expect(shortDate('2026-09-25')).toBe('Sep 25')
    expect(shortDate('2026-01-01')).toBe('Jan 1')
    expect(dateWithYear('2025-09-29')).toBe('Sep 29, 2025')
    expect(dateWithYear('2023-01-01')).toBe('Jan 1, 2023')
  })

  it('reads only the date part of a timestamp', () => {
    expect(shortDate('2026-09-25T23:30:00Z')).toBe('Sep 25')
    expect(dateWithYear('2026-02-18T03:00:00-06:00')).toBe('Feb 18, 2026')
  })

  it('passes through anything it cannot parse', () => {
    expect(shortDate('soon')).toBe('soon')
    expect(dateWithYear('garbage')).toBe('garbage')
  })
})

describe('ctDayKey', () => {
  it('keys a timestamp by its Central calendar day, not the UTC one', () => {
    expect(CENTRAL_TZ).toBe('America/Chicago')
    expect(ctDayKey(Date.parse('2026-11-15T05:30:00Z'))).toBe('2026-11-14')
    expect(ctDayKey(Date.parse('2026-11-15T06:30:00Z'))).toBe('2026-11-15')
  })
})

describe('tourColor', () => {
  it('maps each tour to its theme color, whatever the case', () => {
    expect(tourColor('ATP')).toBe('var(--atp-blue)')
    expect(tourColor('wta')).toBe('var(--wta-pink)')
    expect(tourColor('Challenger')).toBe('var(--challenger-teal)')
  })

  it('reads an unknown tour as secondary text', () => {
    expect(tourColor('ITF')).toBe('var(--text-secondary)')
  })
})
