import { useRef } from 'react'

export function useNflDrawerFocus() {
  const trigger = useRef<HTMLButtonElement | null>(null)
  const rememberTrigger = (lineId: number) => {
    trigger.current = document.querySelector<HTMLButtonElement>(`.prop-table__open[data-line-id="${lineId}"]`)
  }
  const afterOpenChange = (open: boolean) => {
    if (!open) requestAnimationFrame(() => {
      if (trigger.current?.isConnected) trigger.current.focus({ preventScroll: true })
    })
  }
  return { rememberTrigger, afterOpenChange }
}
