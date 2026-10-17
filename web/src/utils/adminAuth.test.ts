import { describe, expect, it } from 'vitest'
import {
  ADMIN_KEY_STORAGE,
  adminKeyHeaders,
  clearAdminKey,
  isAdminRejection,
  readAdminKey,
  storeAdminKey,
} from '~/utils/adminAuth'

class MemoryStorage implements Storage {
  private items = new Map<string, string>()
  get length(): number {
    return this.items.size
  }
  clear(): void {
    this.items.clear()
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null
  }
  removeItem(key: string): void {
    this.items.delete(key)
  }
  setItem(key: string, value: string): void {
    this.items.set(key, value)
  }
}

class BrokenStorage extends MemoryStorage {
  getItem(): string | null {
    throw new Error('SecurityError')
  }
  setItem(): void {
    throw new Error('QuotaExceededError')
  }
  removeItem(): void {
    throw new Error('SecurityError')
  }
}

const KEY = 'k'.repeat(32)

describe('admin key storage', () => {
  it('stores, reads and clears the key', () => {
    const storage = new MemoryStorage()
    expect(storeAdminKey(storage, KEY)).toBe(true)
    expect(readAdminKey(storage)).toBe(KEY)
    expect(storage.getItem(ADMIN_KEY_STORAGE)).toBe(KEY)
    clearAdminKey(storage)
    expect(readAdminKey(storage)).toBeNull()
  })

  it('trims the key and refuses an empty one', () => {
    const storage = new MemoryStorage()
    expect(storeAdminKey(storage, `  ${KEY}\n`)).toBe(true)
    expect(readAdminKey(storage)).toBe(KEY)
    expect(storeAdminKey(storage, '   ')).toBe(false)
    expect(readAdminKey(storage)).toBe(KEY)
  })

  it('reads as signed out when storage is missing or throws', () => {
    const broken = new BrokenStorage()
    expect(readAdminKey(null)).toBeNull()
    expect(readAdminKey(broken)).toBeNull()
    expect(storeAdminKey(null, KEY)).toBe(false)
    expect(storeAdminKey(broken, KEY)).toBe(false)
    expect(() => clearAdminKey(broken)).not.toThrow()
  })
})

describe('adminKeyHeaders', () => {
  it('sends the key to admin routes', () => {
    expect(adminKeyHeaders('/admin/session', KEY)).toEqual({ 'X-API-Key': KEY })
    expect(adminKeyHeaders('/admin/players/1/set-elo', KEY)).toEqual({ 'X-API-Key': KEY })
  })

  it('sends nothing without a key', () => {
    expect(adminKeyHeaders('/admin/session', null)).toEqual({})
  })

  it('never sends the key to a public route', () => {
    expect(adminKeyHeaders('/tennis/predictions/today', KEY)).toEqual({})
    expect(adminKeyHeaders('/administrators', KEY)).toEqual({})
    expect(adminKeyHeaders(undefined, KEY)).toEqual({})
  })
})

describe('isAdminRejection', () => {
  it('is a 401 from an admin route', () => {
    expect(isAdminRejection('/admin/players/flagged', 401)).toBe(true)
  })

  it('ignores other statuses and public routes', () => {
    expect(isAdminRejection('/admin/session', 403)).toBe(false)
    expect(isAdminRejection('/admin/session', 429)).toBe(false)
    expect(isAdminRejection('/admin/session', undefined)).toBe(false)
    expect(isAdminRejection('/nfl/slate', 401)).toBe(false)
  })
})
