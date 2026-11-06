import { describe, expect, it } from 'vitest'
import { defaultSlateDates, utcDatesForCentralDay } from '~/utils/tennisDates'

describe('utcDatesForCentralDay', () => {
  it('covers the chosen UTC date and the next, where Central evenings are stored', () => {
    expect(utcDatesForCentralDay('2026-09-25')).toEqual(['2026-09-25', '2026-09-26'])
  })

  it('rolls over month and year ends', () => {
    expect(utcDatesForCentralDay('2026-09-30')).toEqual(['2026-09-30', '2026-10-01'])
    expect(utcDatesForCentralDay('2026-12-31')).toEqual(['2026-12-31', '2027-01-01'])
  })
})

describe('defaultSlateDates', () => {
  it('is the UTC date of now and the next, whatever the local clock says', () => {
    expect(defaultSlateDates(new Date('2026-11-06T03:30:00Z'))).toEqual(['2026-11-06', '2026-11-07'])
    expect(defaultSlateDates(new Date('2026-11-06T23:59:59Z'))).toEqual(['2026-11-06', '2026-11-07'])
  })

  it('rolls over a month and a DST change', () => {
    expect(defaultSlateDates(new Date('2026-10-31T12:00:00Z'))).toEqual(['2026-10-31', '2026-11-01'])
    expect(defaultSlateDates(new Date('2026-03-08T06:00:00Z'))).toEqual(['2026-03-08', '2026-03-09'])
  })
})
