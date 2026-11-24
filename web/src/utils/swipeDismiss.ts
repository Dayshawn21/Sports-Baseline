export type SwipeDirection = 'right' | 'down'
export type SwipeLock = 'pending' | 'along' | 'across'

export const SWIPE_SLOP = 10
/** The move must lean this much more along the dismiss axis than across it, so diagonal scrolls stay scrolls. */
export const SWIPE_AXIS_RATIO = 1.2
export const DISMISS_DISTANCE_SHARE = 0.35
/** px per ms; a quick flick closes the drawer before it travels the distance share. */
export const DISMISS_SPEED_FLOOR = 0.5
export const DISMISS_FLICK_MIN_DISTANCE = 24

/** Decides, once the finger passes the slop, whether this gesture drags the drawer or belongs to the content. */
export function swipeAxisLock(dx: number, dy: number, direction: SwipeDirection, slop = SWIPE_SLOP): SwipeLock {
  if (Math.hypot(dx, dy) < slop) return 'pending'
  const along = direction === 'right' ? dx : dy
  const across = direction === 'right' ? dy : dx
  return along > 0 && along > Math.abs(across) * SWIPE_AXIS_RATIO ? 'along' : 'across'
}

interface Release {
  /** px moved toward the dismiss edge; negative is backwards. */
  distance: number
  /** px per ms toward the dismiss edge at release; negative is backwards. */
  velocity: number
  /** The panel's size along the dismiss axis, in px. */
  size: number
}

export function shouldDismiss({ distance, velocity, size }: Release): boolean {
  if (distance <= 0 || velocity <= -DISMISS_SPEED_FLOOR) return false
  if (size > 0 && distance >= size * DISMISS_DISTANCE_SHARE) return true
  return velocity >= DISMISS_SPEED_FLOOR && distance >= DISMISS_FLICK_MIN_DISTANCE
}
