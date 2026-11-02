import { describe, expect, it } from 'vitest'
import { openedRowKey, rememberOpenedRow, takeOpenedRow, type OpenedRowStore } from '~/utils/nflOpenedRow'

function memoryStore(): OpenedRowStore & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return { data, getItem: key => data.get(key) ?? null, setItem: (key, value) => { data.set(key, value) }, removeItem: key => { data.delete(key) } }
}

describe('opened row store', () => {
  it('keys a row by where it was opened from', () => {
    expect(openedRowKey('table', 7)).toBe('table:7')
    expect(openedRowKey('digest', 7)).toBe('digest:7')
  })

  it('returns the key for the same path, once', () => {
    const store = memoryStore()
    rememberOpenedRow(store, '#/nfl/board?position=WR', 'table:30')

    expect(takeOpenedRow(store, '#/nfl/board?position=WR')).toBe('table:30')
    expect(takeOpenedRow(store, '#/nfl/board?position=WR')).toBeNull()
  })

  it('does not restore on a different path, and still clears it', () => {
    const store = memoryStore()
    rememberOpenedRow(store, '#/nfl/board', 'table:30')

    expect(takeOpenedRow(store, '#/nfl/game/1')).toBeNull()
    expect(store.data.size).toBe(0)
  })

  it('ignores malformed stored data', () => {
    const store = memoryStore()
    store.setItem('lineform:nfl-opened-row', '{not json')
    expect(takeOpenedRow(store, '#/nfl/board')).toBeNull()
    store.setItem('lineform:nfl-opened-row', JSON.stringify({ path: '#/nfl/board', key: 5 }))
    expect(takeOpenedRow(store, '#/nfl/board')).toBeNull()
    store.setItem('lineform:nfl-opened-row', 'null')
    expect(takeOpenedRow(store, '#/nfl/board')).toBeNull()
  })

  it('does nothing when storage is unavailable or throws', () => {
    expect(() => rememberOpenedRow(null, '#/x', 'table:1')).not.toThrow()
    expect(takeOpenedRow(null, '#/x')).toBeNull()
    const broken: OpenedRowStore = { getItem: () => { throw new Error('blocked') }, setItem: () => { throw new Error('full') }, removeItem: () => undefined }
    expect(() => rememberOpenedRow(broken, '#/x', 'table:1')).not.toThrow()
    expect(takeOpenedRow(broken, '#/x')).toBeNull()
  })
})
