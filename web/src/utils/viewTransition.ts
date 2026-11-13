import { sportForPath } from '~/utils/sportNav'

export interface ViewTransitionInput {
  from: string
  to: string
  navigationType: 'POP' | 'PUSH' | 'REPLACE'
  supported: boolean
  reducedMotion: boolean
}

/**
 * A crossfade only between two different sport pages. Back and Forward stay instant:
 * phone browsers animate swipe-back themselves, and Back restores the opened row.
 */
export function shouldViewTransition({ from, to, navigationType, supported, reducedMotion }: ViewTransitionInput): boolean {
  if (!supported || reducedMotion || navigationType === 'POP') return false
  if (from === to) return false
  return sportForPath(from) !== null && sportForPath(to) !== null
}

export function viewTransitionsSupported(doc: Pick<Document, 'startViewTransition'> | undefined): boolean {
  return typeof doc?.startViewTransition === 'function'
}
