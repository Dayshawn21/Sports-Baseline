// The owner's admin key, held per tab and sent only to /admin routes.

export const ADMIN_KEY_STORAGE = 'sportapp.adminKey'
export const ADMIN_KEY_CHANGED = 'sportapp:admin-key-changed'
const ADMIN_PATH = '/admin'

export function readAdminKey(storage: Storage | null): string | null {
  try {
    return storage?.getItem(ADMIN_KEY_STORAGE) || null
  } catch {
    return null
  }
}

export function storeAdminKey(storage: Storage | null, key: string): boolean {
  const trimmed = key.trim()
  if (!trimmed || !storage) return false
  try {
    storage.setItem(ADMIN_KEY_STORAGE, trimmed)
    return true
  } catch {
    return false
  }
}

export function clearAdminKey(storage: Storage | null): void {
  try {
    storage?.removeItem(ADMIN_KEY_STORAGE)
  } catch {
    // Storage that cannot be written cannot hold a key either.
  }
}

function isAdminUrl(url: string | undefined): boolean {
  return url === ADMIN_PATH || (url?.startsWith(`${ADMIN_PATH}/`) ?? false)
}

export function adminKeyHeaders(url: string | undefined, key: string | null): Record<string, string> {
  return key && isAdminUrl(url) ? { 'X-API-Key': key } : {}
}

export function isAdminRejection(url: string | undefined, status: number | undefined): boolean {
  return status === 401 && isAdminUrl(url)
}

function browserStorage(): Storage | null {
  try {
    return window.sessionStorage
  } catch {
    return null
  }
}

function announce(): void {
  window.dispatchEvent(new Event(ADMIN_KEY_CHANGED))
}

// The `storage` event fires only in other tabs, so this tab announces its own changes.
export const sessionAdminKey = {
  read: (): string | null => readAdminKey(browserStorage()),
  store: (key: string): boolean => {
    const stored = storeAdminKey(browserStorage(), key)
    if (stored) announce()
    return stored
  },
  clear: (): void => {
    clearAdminKey(browserStorage())
    announce()
  },
  subscribe: (onChange: () => void): (() => void) => {
    window.addEventListener(ADMIN_KEY_CHANGED, onChange)
    return () => window.removeEventListener(ADMIN_KEY_CHANGED, onChange)
  },
}
