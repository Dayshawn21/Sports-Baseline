import { describe, expect, it } from 'vitest'
import { STALE_ODDS_MS, countPart, gameSlateLine, isOddsStale, oddsPart, slatePeriodLine, splitTags, startTimes, tableCountPart } from '~/utils/slatePeriod'

const NOW = Date.parse('2026-11-08T22:00:00Z')
const HOUR = 60 * 60 * 1000

describe('slatePeriodLine', () => {
  it('joins the parts with a middle dot', () => {
    expect(slatePeriodLine(['Week 9', '15 games', '1 final', 'odds Tue 3:12 PM CT']))
      .toBe('Week 9 · 15 games · 1 final · odds Tue 3:12 PM CT')
  })

  it('leaves out parts with no value rather than showing a placeholder', () => {
    expect(slatePeriodLine(['Sat, Nov 8', null, '0 final', undefined, '', false, '  '])).toBe('Sat, Nov 8 · 0 final')
  })

  it('returns an empty line when nothing has a value', () => {
    expect(slatePeriodLine([null, undefined])).toBe('')
  })
})

describe('isOddsStale', () => {
  const upcoming = [NOW + HOUR]

  it('is not stale at exactly six hours', () => {
    expect(isOddsStale(NOW - STALE_ODDS_MS, upcoming, NOW)).toBe(false)
  })

  it('is stale just past six hours with a game still to start', () => {
    expect(isOddsStale(NOW - STALE_ODDS_MS - 1, upcoming, NOW)).toBe(true)
  })

  it('is not stale when every game has started', () => {
    expect(isOddsStale(NOW - 10 * HOUR, [NOW - HOUR, NOW], NOW)).toBe(false)
    expect(isOddsStale(NOW - 10 * HOUR, [], NOW)).toBe(false)
  })

  it('is not stale when no odds are stored', () => {
    expect(isOddsStale(null, upcoming, NOW)).toBe(false)
    expect(isOddsStale(Number.NaN, upcoming, NOW)).toBe(false)
  })
})

describe('countPart', () => {
  it('uses the singular for one and the plural otherwise', () => {
    expect(countPart(1, 'game')).toBe('1 game')
    expect(countPart(0, 'final', 'final')).toBe('0 final')
    expect(countPart(33, 'match', 'matches')).toBe('33 matches')
  })
})

describe('startTimes', () => {
  it('keeps parseable start times only', () => {
    expect(startTimes(['2026-11-08T22:00:00Z', null, undefined, '', 'TBD'])).toEqual([NOW])
  })
})

describe('gameSlateLine', () => {
  const counts = { games: 15, finals: 1, oddsUpdated: 'Tue 3:12 PM CT', oddsUpdatedMs: NOW - 2 * HOUR }

  it('builds the period, counts and odds time', () => {
    expect(gameSlateLine('Week 9', counts, [NOW + HOUR], NOW)).toBe('Week 9 · 15 games · 1 final · odds Tue 3:12 PM CT')
  })

  it('marks stale odds while a game is still to start', () => {
    expect(gameSlateLine('Week 9', { ...counts, oddsUpdatedMs: NOW - 7 * HOUR }, [NOW + HOUR], NOW))
      .toBe('Week 9 · 15 games · 1 final · odds Tue 3:12 PM CT (stale)')
  })

  it('leaves out the odds when none are stored, and shows the period alone for an empty slate', () => {
    expect(gameSlateLine('Sun, Nov 8, 2026', { games: 1, finals: 0, oddsUpdated: null, oddsUpdatedMs: null }, [], NOW))
      .toBe('Sun, Nov 8, 2026 · 1 game · 0 final')
    expect(gameSlateLine('Week 12', { ...counts, games: 0 }, [], NOW)).toBe('Week 12')
  })
})

describe('oddsPart', () => {
  it('labels the odds time and marks stale odds in words', () => {
    expect(oddsPart('Tue 3:12 PM CT', false)).toBe('odds Tue 3:12 PM CT')
    expect(oddsPart('Tue 3:12 PM CT', true)).toBe('odds Tue 3:12 PM CT (stale)')
  })

  it('is left out when no odds are stored', () => {
    expect(oddsPart(null, true)).toBeNull()
  })
})

describe('tableCountPart', () => {
  it('counts the whole table when no search is active', () => {
    expect(tableCountPart(7, 7, false, 'game')).toBe('7 games')
    expect(tableCountPart(1, 1, false, 'match', 'matches')).toBe('1 match')
  })

  it('shows the matches out of the whole table while searching, even when all match', () => {
    expect(tableCountPart(1, 7, true, 'game')).toBe('1 of 7 games')
    expect(tableCountPart(20, 20, true, 'match', 'matches')).toBe('20 of 20 matches')
  })
})

describe('splitTags', () => {
  it('keeps the first tags in order and holds the rest back', () => {
    expect(splitTags(['a', 'b', 'c', 'd'], 2)).toEqual({ shown: ['a', 'b'], hidden: ['c', 'd'] })
  })

  it('hides nothing when the tags fit', () => {
    expect(splitTags(['a'], 2)).toEqual({ shown: ['a'], hidden: [] })
    expect(splitTags([], 2)).toEqual({ shown: [], hidden: [] })
  })

  it('treats a negative limit as zero', () => {
    expect(splitTags(['a', 'b'], -1)).toEqual({ shown: [], hidden: ['a', 'b'] })
  })
})
