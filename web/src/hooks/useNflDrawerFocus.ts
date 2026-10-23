import { useRef } from 'react'

export function useNflDrawerFocus() {
  const trigger = useRef<HTMLButtonElement | null>(null)
  /** A digest box passes itself; a table row is found by its line. */
  const rememberTrigger = (lineId: number, element?: HTMLButtonElement) => {
    trigger.current = element ?? document.querySelector<HTMLButtonElement>(`.prop-table__open[data-line-id="${lineId}"]`)
  }
  const afterOpenChange = (open: boolean) => {
    if (!open) requestAnimationFrame(() => {
      if (trigger.current?.isConnected) trigger.current.focus({ preventScroll: true })
    })
  }
  return { rememberTrigger, afterOpenChange }
}
