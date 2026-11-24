import { describe, expect, it } from 'vitest'
import type { NflHistorySample } from '~/types/nfl'
import { formBarLabel, formDateText, formEmptyText, formHistoryDate, formOptions, formSample, formShortNote, formTitle, parseFormWindow, resolveFormWindow } from '~/utils/nflFormWindow'

const sample = (...values: number[]): NflHistorySample => ({
  average: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null,
  values: values.map((value, index) => ({ value, opponentTeam: `T${index}` })),
})

function row(overrides: Partial<Parameters<typeof formOptions>[0]> = {}) {
  return {
    recentForm: sample(5, 4, 3, 2, 1),
    recentFormLong: sample(5, 4, 3, 2, 1, 9, 8, 7, 6, 5),
    opponentHistory: sample(30, 20),
    opponentTeam: 'MIA',
    ...overrides,
  }
}

describe('parseFormWindow', () => {
  it('reads 10 and opp, and falls back to Last 5 for anything else', () => {
    const parse = (query: string) => parseFormWindow(new URLSearchParams(query))
    expect([parse(''), parse('form=10'), parse('form=opp'), parse('form=5'), parse('form=junk')]).toEqual(['5', '10', 'opp', '5', '5'])
  })
})

describe('form window options', () => {
  it('enables all three windows when the row has the data', () => {
    expect(formOptions(row()).map(option => [option.label, option.disabledReason])).toEqual([['Last 5', null], ['Last 10', null], ['vs MIA', null]])
  })

  it('disables Last 10 for a stale snapshot and vs Opponent without an opponent', () => {
    const options = formOptions(row({ recentFormLong: undefined, opponentTeam: null }))
    expect(options.map(option => option.disabledReason)).toEqual([null, 'Not in this slate snapshot yet', 'No opponent this week'])
    expect(resolveFormWindow(row({ recentFormLong: undefined }), '10')).toBe('5')
    expect(resolveFormWindow(row({ opponentTeam: null }), 'opp')).toBe('5')
  })
})

describe('formSample', () => {
  it('reads the sample behind each window', () => {
    expect(formSample(row(), '5').values).toHaveLength(5)
    expect(formSample(row(), '10').values).toHaveLength(10)
    expect(formSample(row(), 'opp').values.map(item => item.value)).toEqual([30, 20])
  })

  it('shows Last 5 content when the chosen window is unavailable', () => {
    const stale = row({ recentFormLong: undefined })
    expect(formSample(stale, '10')).toBe(stale.recentForm)
  })
})

describe('labels and states', () => {
  it('titles each window', () => {
    expect([formTitle(row(), '5'), formTitle(row(), '10'), formTitle(row(), 'opp')]).toEqual(['Recent form', 'Last 10', 'Vs MIA'])
  })

  it('notes a short Last 10 and nothing for the other windows', () => {
    expect(formShortNote(row({ recentFormLong: sample(1, 2, 3, 4, 5, 6, 7) }), '10')).toBe('7 of 10 games')
    expect(formShortNote(row(), '10')).toBeNull()
    expect(formShortNote(row({ recentFormLong: sample(1, 2, 3, 4, 5, 6, 7) }), '5')).toBeNull()
  })

  it('explains an empty vs Opponent window by opponent and start year', () => {
    expect(formEmptyText(row({ opponentHistory: sample() }), 'opp')).toBe('No earlier games against MIA since 2024.')
    expect(formEmptyText(row(), '5')).toBe('No completed history')
  })

  it('takes the history start year from the sport', () => {
    expect(formEmptyText(row({ opponentHistory: sample() }), 'opp', 2023)).toBe('No earlier games against MIA since 2023.')
    expect(formEmptyText(row(), '5', 2023)).toBe('No completed history')
  })
})

describe('formHistoryDate', () => {
  const now = new Date('2026-11-02T12:00:00Z')

  it('reads the date as written and adds a year only for an earlier NFL season', () => {
    expect(formHistoryDate('2026-10-12', now)).toEqual({ month: 'Oct', day: 12, year: null })
    expect(formHistoryDate('2025-09-07', now)).toEqual({ month: 'Sep', day: 7, year: "'25" })
    expect(formDateText(formHistoryDate('2025-09-07', now))).toBe("Sep 7 '25")
    expect(formDateText(formHistoryDate('2026-01-04', now))).toBe("Jan 4 '26")
  })

  it('returns null for a missing or malformed date', () => {
    expect([formHistoryDate(null, now), formHistoryDate(undefined, now), formHistoryDate('', now), formHistoryDate('10/12/2026', now), formHistoryDate('2026-13-01', now)]).toEqual([null, null, null, null, null])
    expect(formDateText(null)).toBeNull()
  })
})

describe('formHistoryDate in January', () => {
  it('keeps the year off a game from the same season', () => {
    const january = new Date('2027-01-10T12:00:00Z')
    expect(formDateText(formHistoryDate('2026-12-20', january))).toBe('Dec 20')
    expect(formDateText(formHistoryDate('2027-01-03', january))).toBe('Jan 3')
    expect(formDateText(formHistoryDate('2026-01-04', january))).toBe("Jan 4 '26")
  })
})

describe('formBarLabel', () => {
  it('drops the decimal from a whole count and keeps it for a fraction', () => {
    expect([formBarLabel(271), formBarLabel(0), formBarLabel(13.5), formBarLabel(28.4), formBarLabel(-2), formBarLabel(-1.5)]).toEqual(['271', '0', '13.5', '28.4', '-2', '-1.5'])
  })
})

describe('formHistoryDate with an August season start (NBA, NHL)', () => {
  const AUGUST = 7
  const text = (date: string, now: string) => formDateText(formHistoryDate(date, new Date(`${now}T12:00:00Z`), AUGUST))

  it('shows the year on a game from the previous season, including its spring playoffs', () => {
    expect(text('2026-04-18', '2026-11-02')).toBe("Apr 18 '26")
    expect(text('2026-10-12', '2026-11-02')).toBe('Oct 12')
    expect(text('2027-04-18', '2027-05-01')).toBe('Apr 18')
    expect(text('2027-01-05', '2027-11-02')).toBe("Jan 5 '27")
  })

  it('treats a game before the August rollover as the earlier season', () => {
    expect(text('2026-07-30', '2026-11-02')).toBe("Jul 30 '26")
    expect(text('2026-08-01', '2026-11-02')).toBe('Aug 1')
  })

  it('leaves the NFL default untouched', () => {
    const now = new Date('2026-11-02T12:00:00Z')
    expect(formHistoryDate('2026-04-18', now)).toEqual(formHistoryDate('2026-04-18', now, 2))
    expect(formDateText(formHistoryDate('2026-04-18', now))).toBe('Apr 18')
  })
})
