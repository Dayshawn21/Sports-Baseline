import { describe, expect, it } from 'vitest'
import { nflWeekKey, nflWeekNeighbors, nflWeekPath, nflWeekPickerOptions, parseNflWeekKey, readNflWeekLink } from '~/utils/nflWeekPeriod'

describe('nflWeekNeighbors', () => {
  it('steps one week inside a season', () => {
    expect(nflWeekNeighbors({ season: 2026, week: 9 })).toEqual({
      previous: { season: 2026, week: 8 },
      next: { season: 2026, week: 10 },
    })
  })

  it('wraps week 1 back to the previous season week 18, and week 18 forward to the next season', () => {
    expect(nflWeekNeighbors({ season: 2026, week: 1 }).previous).toEqual({ season: 2025, week: 18 })
    expect(nflWeekNeighbors({ season: 2025, week: 18 }).next).toEqual({ season: 2026, week: 1 })
  })

  it('reaches the 2024 historical season', () => {
    expect(nflWeekNeighbors({ season: 2025, week: 1 }).previous).toEqual({ season: 2024, week: 18 })
    expect(nflWeekNeighbors({ season: 2024, week: 18 }).next).toEqual({ season: 2025, week: 1 })
  })

  it('has no next after the newest week 18 and no previous before the oldest week 1', () => {
    expect(nflWeekNeighbors({ season: 2026, week: 18 }).next).toBeNull()
    expect(nflWeekNeighbors({ season: 2024, week: 1 }).previous).toBeNull()
  })
})

describe('readNflWeekLink', () => {
  it('reads a listed season and a week 1-18', () => {
    expect(readNflWeekLink(new URLSearchParams('season=2025&week=18'))).toEqual({ season: 2025, week: 18 })
  })

  it('treats missing or invalid values as the current week', () => {
    expect(readNflWeekLink(new URLSearchParams(''))).toEqual({ season: null, week: null })
    expect(readNflWeekLink(new URLSearchParams('season=1999&week=19'))).toEqual({ season: null, week: null })
    expect(readNflWeekLink(new URLSearchParams('season=abc&week=2.5'))).toEqual({ season: null, week: null })
    expect(readNflWeekLink(new URLSearchParams('season=&week=0'))).toEqual({ season: null, week: null })
  })
})

describe('week keys and paths', () => {
  it('round-trips the picker key and builds the slate link', () => {
    expect(parseNflWeekKey(nflWeekKey({ season: 2024, week: 3 }))).toEqual({ season: 2024, week: 3 })
    expect(parseNflWeekKey('2023-3')).toBeNull()
    expect(nflWeekPath({ season: 2026, week: 9 })).toBe('/nfl?season=2026&week=9')
  })

  it('groups 18 weeks under each listed season, newest first', () => {
    const groups = nflWeekPickerOptions()
    expect(groups.map(group => group.label)).toEqual(['2026', '2025', '2024 historical'])
    expect(groups.every(group => group.options.length === 18)).toBe(true)
    expect(groups[2].options[0]).toEqual({ value: '2024-1', label: 'Week 1' })
  })
})
