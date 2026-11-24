import { describe, expect, it } from 'vitest'
import { defaultSlateDates, defaultTennisDay, tennisDateNeighbors, utcDatesForCentralDay } from '~/utils/tennisDates'

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
  it('steps one day either side', () => {
    expect(tennisDateNeighbors('2026-11-12')).toEqual({ previous: '2026-11-11', next: '2026-11-13' })
  })

  it('crosses a month and a year end', () => {
    expect(tennisDateNeighbors('2026-11-30')).toEqual({ previous: '2026-11-29', next: '2026-12-01' })
    expect(tennisDateNeighbors('2026-12-31')).toEqual({ previous: '2026-12-30', next: '2027-01-01' })
    expect(tennisDateNeighbors('2027-03-01')).toEqual({ previous: '2027-02-28', next: '2027-03-02' })
  })
})

describe('defaultTennisDay', () => {
  // 8:00 PM CST on Sun, Nov 8, 2026.
  const EVENING = Date.parse('2026-11-09T02:00:00Z')

  it('keeps today while one of its matches is still to start', () => {
    expect(defaultTennisDay(['2026-11-08T20:00:00Z', '2026-11-09T04:30:00Z'], EVENING)).toBe('2026-11-08')
  })

  it('rolls to tomorrow once every match today has started', () => {
    expect(defaultTennisDay(['2026-11-08T20:00:00Z', '2026-11-09T01:59:00Z'], EVENING)).toBe('2026-11-09')
  })

  it('rolls to tomorrow when today has no matches', () => {
    expect(defaultTennisDay([], EVENING)).toBe('2026-11-09')
  })

  it('counts a 2 AM CT match as tomorrow, not today', () => {
    expect(defaultTennisDay(['2026-11-09T08:00:00Z'], EVENING)).toBe('2026-11-09')
  })

  it('splits days at CT midnight', () => {
    expect(defaultTennisDay(['2026-11-09T05:59:00Z'], EVENING)).toBe('2026-11-08')
    expect(defaultTennisDay(['2026-11-09T06:00:00Z'], EVENING)).toBe('2026-11-09')
  })

  it('reads CT across both DST changes', () => {
    // 11:30 PM CDT on Oct 31, then 12:30 AM CDT on Nov 1, the fall-back day.
    expect(defaultTennisDay(['2026-11-01T04:30:00Z'], Date.parse('2026-11-01T04:00:00Z'))).toBe('2026-10-31')
    expect(defaultTennisDay(['2026-11-01T05:30:00Z'], Date.parse('2026-11-01T04:00:00Z'))).toBe('2026-11-01')
    // 11:30 PM CST on Mar 13, the night clocks spring forward.
    expect(defaultTennisDay(['2027-03-14T05:30:00Z'], Date.parse('2027-03-14T04:00:00Z'))).toBe('2027-03-13')
  })

  it('ignores missing and unreadable times', () => {
    expect(defaultTennisDay([null, 'not a date'], EVENING)).toBe('2026-11-09')
  })

  it('rolls over a year end', () => {
    expect(defaultTennisDay([], Date.parse('2026-12-31T23:00:00Z'))).toBe('2027-01-01')
  })
})
