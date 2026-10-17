import { describe, expect, it } from 'vitest'
import { utcDatesForCentralDay } from '~/utils/tennisDates'

describe('utcDatesForCentralDay', () => {
  it('covers the chosen UTC date and the next, where Central evenings are stored', () => {
    expect(utcDatesForCentralDay('2026-09-25')).toEqual(['2026-09-25', '2026-09-26'])
  })

  it('rolls over month and year ends', () => {
    expect(utcDatesForCentralDay('2026-09-30')).toEqual(['2026-09-30', '2026-10-01'])
    expect(utcDatesForCentralDay('2026-12-31')).toEqual(['2026-12-31', '2027-01-01'])
  })
})
