import { useEffect, useRef } from 'react'
import { useNavigationType } from 'react-router-dom'
import { openedRowKey, rememberOpenedRow, sessionOpenedRowStore, takeOpenedRow } from '~/utils/nflOpenedRow'

/** Remembers which row or digest box was followed. The router keeps the path in the fragment, so that is the page's identity. */
export function rememberOpened(source: 'table' | 'digest', lineId: number): void {
  rememberOpenedRow(sessionOpenedRowStore(), window.location.hash, openedRowKey(source, lineId))
}

/** On Back, once the rows exist, focuses the row that was opened and scrolls it to the middle. A fresh visit never moves focus. */
export function useRestoreOpenedRow(ready: boolean): void {
  const navigationType = useNavigationType()
  const done = useRef(false)
  useEffect(() => {
    if (!ready || done.current || navigationType !== 'POP') return
    done.current = true
    const key = takeOpenedRow(sessionOpenedRowStore(), window.location.hash)
    if (key === null) return
    const target = document.querySelector<HTMLElement>(`[data-open-key="${key}"]`)
    target?.focus({ preventScroll: true })
    target?.scrollIntoView({ block: 'center' })
  }, [ready, navigationType])
}
