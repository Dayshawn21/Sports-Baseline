import { describe, expect, it } from 'vitest'
import type { NflHistorySample } from '~/types/nfl'
import { formEmptyText, formOptions, formSample, formShortNote, formTitle, parseFormWindow, resolveFormWindow } from '~/utils/nflFormWindow'

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
})
