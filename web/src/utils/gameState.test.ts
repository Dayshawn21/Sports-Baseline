import { describe, expect, it } from 'vitest'
import { gameStartLabel, gameStartParts, gameState, withEndPeriod } from '~/utils/gameState'

const START = '2026-11-09T18:00:00Z'
const at = (iso: string) => new Date(iso)

describe('gameState', () => {
  it('is scheduled before the start', () => {
    expect(gameState('scheduled', START, at('2026-11-09T17:59:00Z'))).toEqual({ phase: 'upcoming', label: 'Scheduled' })
  })

  it('is in progress once the clock passes the start, though the stored status still says scheduled', () => {
    expect(gameState('scheduled', START, at('2026-11-09T18:00:00Z'))).toEqual({ phase: 'live', label: 'In progress' })
    expect(gameState('scheduled', START, at('2026-11-09T20:30:00Z'))).toEqual({ phase: 'live', label: 'In progress' })
  })

  it('is result pending once the game is over by the clock with no final stored', () => {
    expect(gameState('scheduled', START, at('2026-11-10T06:00:00Z'))).toEqual({ phase: 'pending', label: 'Result pending' })
  })

  it('is final when completed, whatever the clock says', () => {
    expect(gameState('completed', START, at('2026-11-09T17:00:00Z'))).toEqual({ phase: 'final', label: 'Final' })
    expect(gameState('Completed', START, at('2026-11-12T00:00:00Z')).phase).toBe('final')
  })

  it('is off when postponed or canceled', () => {
    expect(gameState('postponed', START, at('2026-11-09T20:00:00Z'))).toEqual({ phase: 'off', label: 'Postponed' })
    expect(gameState('canceled', START, at('2026-11-09T20:00:00Z'))).toEqual({ phase: 'off', label: 'Canceled' })
  })

  it('stays scheduled without a usable start time', () => {
    expect(gameState('scheduled', null, at('2026-11-09T20:00:00Z')).phase).toBe('upcoming')
    expect(gameState('scheduled', 'not a time', at('2026-11-09T20:00:00Z')).phase).toBe('upcoming')
  })
})

describe('start labels', () => {
  it('writes the start in Central time', () => {
    expect(gameStartLabel(START)).toBe('Mon, Nov 9, 12:00 PM CT')
    expect(gameStartParts(START)).toEqual({ clock: '12:00 PM CT', day: 'Mon, Nov 9' })
  })

  it('uses the CT calendar day across midnight UTC', () => {
    expect(gameStartParts('2026-11-10T01:15:00Z')).toEqual({ clock: '7:15 PM CT', day: 'Mon, Nov 9' })
  })

  it('says when no time is set', () => {
    expect(gameStartLabel(null)).toBe('Start time not set')
    expect(gameStartParts(null)).toBeNull()
  })
})

describe('withEndPeriod', () => {
  const final = gameState('completed', START, at('2026-11-10T00:00:00Z'))

  it('names an overtime or shootout final', () => {
    expect(withEndPeriod(final, 'OT').label).toBe('Final/OT')
    expect(withEndPeriod(final, 'SO').label).toBe('Final/SO')
  })

  it('leaves regulation finals and unfinished games alone', () => {
    expect(withEndPeriod(final, 'REG').label).toBe('Final')
    expect(withEndPeriod(gameState('scheduled', START, at('2026-11-09T19:00:00Z')), 'OT').label).toBe('In progress')
  })
})
