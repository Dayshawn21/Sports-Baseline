import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, SPORTS, navKeyForPath, sportViewForPath, sportViews, visibleNavItems } from '~/utils/sportNav'

describe('navKeyForPath', () => {
  it('highlights the sport on both of its views', () => {
    expect(navKeyForPath('/')).toBe('/')
    expect(navKeyForPath('/tennis/board')).toBe('/')
    expect(navKeyForPath('/tennis/model')).toBe('/')
    expect(navKeyForPath('/nfl')).toBe('/nfl')
    expect(navKeyForPath('/nfl/board')).toBe('/nfl')
    expect(navKeyForPath('/nfl/model')).toBe('/nfl')
    expect(navKeyForPath('/nba')).toBe('/nba')
  })

  it('highlights the sport on its detail pages', () => {
    expect(navKeyForPath('/nfl/game/52')).toBe('/nfl')
    expect(navKeyForPath('/nba/game/21320')).toBe('/nba')
    expect(navKeyForPath('/tennis/match/82864')).toBe('/')
    expect(navKeyForPath('/tennis/player/7')).toBe('/')
  })

  it('keeps the other entries as they are', () => {
    expect(navKeyForPath('/how-it-works')).toBe('/how-it-works')
    expect(navKeyForPath('/admin')).toBe('/admin')
  })

  it('falls back to Tennis for unknown paths', () => {
    expect(navKeyForPath('/parlays')).toBe('/')
    expect(navKeyForPath('/nope')).toBe('/')
  })
})

describe('sportViewForPath', () => {
  it('maps each sport route to its view', () => {
    expect(sportViewForPath('/')).toBe('slate')
    expect(sportViewForPath('/tennis/board')).toBe('props')
    expect(sportViewForPath('/tennis/model')).toBe('model')
    expect(sportViewForPath('/nfl')).toBe('slate')
    expect(sportViewForPath('/nfl/board')).toBe('props')
    expect(sportViewForPath('/nfl/model')).toBe('model')
    expect(sportViewForPath('/nba')).toBe('slate')
    expect(sportViewForPath('/nba/model')).toBe('model')
  })

  it('returns null off the sport routes', () => {
    expect(sportViewForPath('/admin')).toBeNull()
  })
})

describe('sportViews', () => {
  it('gives both sports slate, props and model views', () => {
    expect(sportViews('tennis')).toEqual([
      { view: 'slate', path: '/' },
      { view: 'props', path: '/tennis/board' },
      { view: 'model', path: '/tennis/model' },
    ])
    expect(sportViews('nfl')).toEqual([
      { view: 'slate', path: '/nfl' },
      { view: 'props', path: '/nfl/board' },
      { view: 'model', path: '/nfl/model' },
    ])
  })
})

describe('SPORTS registry', () => {
  it('builds the nav entries, in order', () => {
    expect(NAV_ITEMS).toEqual([
      { key: '/', label: 'Tennis' },
      { key: '/nfl', label: 'NFL' },
      { key: '/nba', label: 'NBA' },
      { key: '/how-it-works', label: 'How it works' },
      { key: '/admin', label: 'Admin' },
    ])
  })

  it('never gives two views the same path', () => {
    const paths = SPORTS.flatMap(sport => sportViews(sport.code).map(entry => entry.path))
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('keeps every view except the root slate under its sport prefix', () => {
    for (const sport of SPORTS) {
      for (const { path } of sportViews(sport.code)) {
        if (path !== '/') expect(`${path}/`.startsWith(sport.prefix)).toBe(true)
      }
    }
  })
})

describe('NBA', () => {
  it('has a slate and a track record page, and no props view until it has a prop board', () => {
    expect(sportViews('nba')).toEqual([{ view: 'slate', path: '/nba' }, { view: 'model', path: '/nba/model' }])
  })
})

describe('visibleNavItems', () => {
  it('hides Admin from visitors', () => {
    expect(visibleNavItems(NAV_ITEMS, false).map(item => item.key)).toEqual(['/', '/nfl', '/nba', '/how-it-works'])
  })

  it('shows Admin to the signed-in owner', () => {
    expect(visibleNavItems(NAV_ITEMS, true)).toEqual(NAV_ITEMS)
  })

  it('keeps highlighting /admin while the entry is hidden', () => {
    expect(navKeyForPath('/admin')).toBe('/admin')
  })
})
