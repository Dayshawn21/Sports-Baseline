import { useEffect, useLayoutEffect, useRef } from 'react'
import { usePrefersReducedMotion } from '~/hooks/usePrefersReducedMotion'
import { shouldDismiss, swipeAxisLock, type SwipeDirection, type SwipeLock } from '~/utils/swipeDismiss'

interface Options {
  direction: SwipeDirection
  open: boolean
  enabled?: boolean
  onDismiss: () => void
}

const SETTLE_MS = 200
// Ant Design's drawer leaves over 0.3s; inline styles must outlast it or the panel jumps back mid-close.
const CLEAR_AFTER_CLOSE_MS = 400
const EXCLUDED = 'input, textarea, select, [contenteditable=""], [contenteditable="true"]'

function parts(panel: HTMLElement) {
  const wrapper = panel.parentElement
  const mask = wrapper?.parentElement?.querySelector<HTMLElement>(':scope > .ant-drawer-mask') ?? null
  return { wrapper, mask }
}

function clearStyles(panel: HTMLElement) {
  const { wrapper, mask } = parts(panel)
  for (const element of [wrapper, mask]) {
    if (!element) continue
    element.style.removeProperty('transform')
    element.style.removeProperty('transition')
    element.style.removeProperty('opacity')
  }
}

function scrollsSideways(target: Element, panel: HTMLElement): boolean {
  for (let node: Element | null = target; node && node !== panel; node = node.parentElement) {
    if (node.scrollWidth > node.clientWidth && /auto|scroll/.test(getComputedStyle(node).overflowX)) return true
  }
  return false
}

function startsExcluded(target: EventTarget | null, panel: HTMLElement, direction: SwipeDirection): boolean {
  if (!(target instanceof Element)) return true
  if (target.closest(EXCLUDED)) return true
  if (direction === 'right') return scrollsSideways(target, panel)
  const body = panel.querySelector('.ant-drawer-body')
  return body !== null && body.scrollTop > 0
}

function place(panel: HTMLElement, direction: SwipeDirection, offset: number, transition: string) {
  const { wrapper, mask } = parts(panel)
  if (!wrapper) return
  const size = direction === 'right' ? wrapper.offsetWidth : wrapper.offsetHeight
  wrapper.style.transition = transition
  wrapper.style.transform = direction === 'right' ? `translateX(${offset}px)` : `translateY(${offset}px)`
  if (mask) {
    mask.style.transition = transition.replace('transform', 'opacity')
    mask.style.opacity = String(size > 0 ? Math.max(0, 1 - offset / size) : 1)
  }
}

/** Touch-drags a drawer panel toward the edge it came from and closes it past the threshold. */
export function useSwipeToDismiss(panel: HTMLElement | null, { direction, open, enabled = true, onDismiss }: Options): void {
  const reduced = usePrefersReducedMotion()
  // Read through a ref so a new onDismiss each render does not re-attach listeners mid-drag.
  const dismissRef = useRef(onDismiss)
  useEffect(() => { dismissRef.current = onDismiss }, [onDismiss])

  // Before the opening frame paints, drop any offset a previous swipe left behind.
  useLayoutEffect(() => {
    if (open && panel) clearStyles(panel)
  }, [open, panel])

  useEffect(() => {
    if (!panel || !open || !enabled) return
    return attachSwipe(panel, direction, reduced, () => dismissRef.current())
  }, [panel, open, enabled, direction, reduced])

  useEffect(() => {
    if (open || !panel) return
    const timer = window.setTimeout(() => clearStyles(panel), CLEAR_AFTER_CLOSE_MS)
    return () => window.clearTimeout(timer)
  }, [open, panel])
}

interface Gesture {
  id: number
  x: number
  y: number
  lock: SwipeLock
  offset: number
  velocity: number
  time: number
}

function attachSwipe(panel: HTMLElement, direction: SwipeDirection, reduced: boolean, onDismiss: () => void): () => void {
  let gesture: Gesture | null = null
  const ease = (property: string) => (reduced ? 'none' : `${property} ${SETTLE_MS}ms ease-out`)
  const previousTouchAction = panel.style.touchAction
  // The browser decides on pointerdown whether it owns the gesture; leave it only the cross axis.
  panel.style.touchAction = direction === 'right' ? 'pan-y pinch-zoom' : 'pan-x pinch-zoom'

  const down = (event: PointerEvent) => {
    if (event.pointerType !== 'touch' || gesture || startsExcluded(event.target, panel, direction)) return
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, lock: 'pending', offset: 0, velocity: 0, time: event.timeStamp }
  }

  const move = (event: PointerEvent) => {
    if (!gesture || event.pointerId !== gesture.id) return
    const dx = event.clientX - gesture.x
    const dy = event.clientY - gesture.y
    if (gesture.lock === 'pending') {
      gesture.lock = swipeAxisLock(dx, dy, direction)
      if (gesture.lock === 'across') { gesture = null; return }
      if (gesture.lock === 'pending') return
      try { panel.setPointerCapture(event.pointerId) } catch { /* synthetic pointers cannot always be captured */ }
    }
    event.preventDefault()
    const offset = Math.max(0, direction === 'right' ? dx : dy)
    const elapsed = event.timeStamp - gesture.time
    if (elapsed > 0) gesture.velocity = 0.8 * ((offset - gesture.offset) / elapsed) + 0.2 * gesture.velocity
    gesture.offset = offset
    gesture.time = event.timeStamp
    place(panel, direction, offset, 'none')
  }

  const end = (event: PointerEvent) => {
    if (!gesture || event.pointerId !== gesture.id) return
    const { lock, offset, velocity } = gesture
    gesture = null
    if (lock !== 'along') return
    const { wrapper } = parts(panel)
    const size = wrapper ? (direction === 'right' ? wrapper.offsetWidth : wrapper.offsetHeight) : 0
    if (event.type === 'pointerup' && shouldDismiss({ distance: offset, velocity, size })) {
      place(panel, direction, size, ease('transform'))
      window.setTimeout(onDismiss, reduced ? 0 : SETTLE_MS)
      return
    }
    place(panel, direction, 0, ease('transform'))
    window.setTimeout(() => clearStyles(panel), reduced ? 0 : SETTLE_MS)
  }

  panel.addEventListener('pointerdown', down)
  panel.addEventListener('pointermove', move)
  panel.addEventListener('pointerup', end)
  panel.addEventListener('pointercancel', end)
  return () => {
    panel.removeEventListener('pointerdown', down)
    panel.removeEventListener('pointermove', move)
    panel.removeEventListener('pointerup', end)
    panel.removeEventListener('pointercancel', end)
    panel.style.touchAction = previousTouchAction
  }
}
