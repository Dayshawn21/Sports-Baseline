import { describe, expect, it } from 'vitest'
import { boardPrefetchTarget } from '~/utils/boardRoute'

describe('boardPrefetchTarget', () => {
  it('reads the sport and date of a props board hash', () => {
    expect(boardPrefetchTarget('#/nba/props')).toEqual({ sport: 'nba', date: null })
    expect(boardPrefetchTarget('#/nba/props?date=2026-11-20&market=points')).toEqual({ sport: 'nba', date: '2026-11-20' })
    expect(boardPrefetchTarget('#/nhl/props')).toEqual({ sport: 'nhl', date: null })
  })

  it('prefetches the default date for a bad date, as the page does', () => {
    expect(boardPrefetchTarget('#/nba/props?date=2026-02-31')).toEqual({ sport: 'nba', date: null })
  })

  it('ignores every other route', () => {
    for (const hash of ['', '#/', '#/nba', '#/nba/props/x', '#/nfl/props', '#/tennis/props', '#/nba/game/7']) {
      expect(boardPrefetchTarget(hash)).toBeNull()
    }
  })
})
