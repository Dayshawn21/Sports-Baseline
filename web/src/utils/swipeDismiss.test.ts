import { describe, expect, it } from 'vitest'
import { DISMISS_FLICK_MIN_DISTANCE, DISMISS_SPEED_FLOOR, SWIPE_SLOP, shouldDismiss, swipeAxisLock } from './swipeDismiss'

describe('swipeAxisLock', () => {
  it('waits inside the slop', () => {
    expect(swipeAxisLock(4, 3, 'right')).toBe('pending')
    expect(swipeAxisLock(0, SWIPE_SLOP - 1, 'down')).toBe('pending')
  })

  it('locks along for a move toward the dismiss edge', () => {
    expect(swipeAxisLock(30, 5, 'right')).toBe('along')
    expect(swipeAxisLock(-4, 30, 'down')).toBe('along')
  })

  it('locks across for a mostly perpendicular move', () => {
    expect(swipeAxisLock(8, 30, 'right')).toBe('across')
    expect(swipeAxisLock(30, 8, 'down')).toBe('across')
  })

  it('locks across for a near-diagonal move', () => {
    expect(swipeAxisLock(20, 19, 'right')).toBe('across')
  })

  it('locks across for a move away from the dismiss edge', () => {
    expect(swipeAxisLock(-30, 0, 'right')).toBe('across')
    expect(swipeAxisLock(0, -30, 'down')).toBe('across')
  })
})

describe('shouldDismiss', () => {
  it('dismisses past the distance share of the panel', () => {
    expect(shouldDismiss({ distance: 140, velocity: 0.1, size: 375 })).toBe(true)
  })

  it('springs back from a slow short drag', () => {
    expect(shouldDismiss({ distance: 40, velocity: 0.1, size: 375 })).toBe(false)
  })

  it('dismisses a fast flick past the minimum distance', () => {
    expect(shouldDismiss({ distance: DISMISS_FLICK_MIN_DISTANCE, velocity: DISMISS_SPEED_FLOOR, size: 375 })).toBe(true)
  })

  it('ignores a fast flick below the minimum distance', () => {
    expect(shouldDismiss({ distance: DISMISS_FLICK_MIN_DISTANCE - 1, velocity: 2, size: 375 })).toBe(false)
  })

  it('never dismisses a backward release', () => {
    expect(shouldDismiss({ distance: -50, velocity: 1, size: 375 })).toBe(false)
    expect(shouldDismiss({ distance: 0, velocity: 1, size: 375 })).toBe(false)
  })

  it('cancels when the finger flicks back after a long drag', () => {
    expect(shouldDismiss({ distance: 200, velocity: -DISMISS_SPEED_FLOOR, size: 375 })).toBe(false)
  })

  it('handles a zero-size panel without the distance share', () => {
    expect(shouldDismiss({ distance: 100, velocity: 0, size: 0 })).toBe(false)
    expect(shouldDismiss({ distance: 100, velocity: 1, size: 0 })).toBe(true)
  })
})
