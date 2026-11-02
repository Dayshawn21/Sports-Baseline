const STORAGE_KEY = 'lineform:nfl-opened-row'

export interface OpenedRowStore {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export function openedRowKey(source: 'table' | 'digest', lineId: number): string {
  return `${source}:${lineId}`
}

export function rememberOpenedRow(store: OpenedRowStore | null, path: string, key: string): void {
  try {
    store?.setItem(STORAGE_KEY, JSON.stringify({ path, key }))
  } catch {
    // Storage can be full or blocked; the row just is not restored.
  }
}

/** The remembered key when it was saved for this path; read once, so a later visit never replays it. */
export function takeOpenedRow(store: OpenedRowStore | null, path: string): string | null {
  try {
    const raw = store?.getItem(STORAGE_KEY)
    if (!raw) return null
    store?.removeItem(STORAGE_KEY)
    const saved: unknown = JSON.parse(raw)
    if (typeof saved !== 'object' || saved === null) return null
    const { path: savedPath, key } = saved as { path?: unknown, key?: unknown }
    return savedPath === path && typeof key === 'string' ? key : null
  } catch {
    return null
  }
}

export function sessionOpenedRowStore(): OpenedRowStore | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}
