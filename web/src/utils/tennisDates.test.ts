import { describe, expect, it } from 'vitest'
import { defaultSlateDates, tennisDateNeighbors, utcDatesForCentralDay } from '~/utils/tennisDates'

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

describe('tennisDateNeighbors', () => {
  it('steps past the two-day view: yesterday and the day after tomorrow', () => {
    expect(tennisDateNeighbors(null, '2026-11-08')).toEqual({ previous: '2026-11-07', next: '2026-11-10' })
  })

  it('steps one day from a single date', () => {
    expect(tennisDateNeighbors('2026-11-12', '2026-11-08')).toEqual({ previous: '2026-11-11', next: '2026-11-13' })
  })

  it('crosses a month and a year end', () => {
    expect(tennisDateNeighbors('2026-11-30', '2026-11-08')).toEqual({ previous: '2026-11-29', next: '2026-12-01' })
    expect(tennisDateNeighbors(null, '2026-12-30')).toEqual({ previous: '2026-12-29', next: '2027-01-01' })
    expect(tennisDateNeighbors('2027-03-01', '2027-03-01')).toEqual({ previous: '2027-02-28', next: '2027-03-02' })
  })
})
