import { describe, expect, it } from 'vitest'
import { SPORTS, documentTitle, menuSections, shellNav, sportViewForPath, sportViews, visibleNavItems } from '~/utils/sportNav'

describe('sportViewForPath', () => {
  it('maps each sport route to its view', () => {
    expect(sportViewForPath('/')).toBe('slate')
    expect(sportViewForPath('/tennis/board')).toBe('props')
    expect(sportViewForPath('/tennis/model')).toBe('model')
    expect(sportViewForPath('/nfl')).toBe('slate')
    expect(sportViewForPath('/nfl/board')).toBe('props')
    expect(sportViewForPath('/nfl/model')).toBe('model')
    expect(sportViewForPath('/nba')).toBe('slate')
    expect(sportViewForPath('/nba/board')).toBe('props')
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
  it('has slate, props and model views', () => {
    expect(sportViews('nba')).toEqual([
      { view: 'slate', path: '/nba' }, { view: 'props', path: '/nba/board' }, { view: 'model', path: '/nba/model' },
    ])
  })

  it('names the Props view in the document title', () => {
    expect(documentTitle('/nba/board')).toBe('NBA props · Lineform')
  })
})

describe('visibleNavItems', () => {
  const items = [{ key: '/nfl' }, { key: '/how-it-works' }, { key: '/admin' }]

  it('hides Admin from visitors', () => {
    expect(visibleNavItems(items, false).map(item => item.key)).toEqual(['/nfl', '/how-it-works'])
  })

  it('shows Admin to the signed-in owner', () => {
    expect(visibleNavItems(items, true)).toEqual(items)
  })
})

describe('shellNav', () => {
  const active = <T extends { active: boolean }>(items: T[]) => items.filter(item => item.active)

  it('marks the sport and view of each sport route', () => {
    const nfl = shellNav('/nfl/board', false)
    expect(nfl.sports.map(sport => [sport.label, sport.path, sport.active])).toEqual([
      ['Tennis', '/', false], ['NFL', '/nfl', true], ['NBA', '/nba', false],
    ])
    expect(nfl.views).toEqual([
      { view: 'slate', label: 'Slate', path: '/nfl', active: false },
      { view: 'props', label: 'Props', path: '/nfl/board', active: true },
      { view: 'model', label: 'Model', path: '/nfl/model', active: false },
    ])
    expect(active(shellNav('/', false).sports).map(sport => sport.code)).toEqual(['tennis'])
    expect(active(shellNav('/', false).views).map(view => view.view)).toEqual(['slate'])
  })

  it('lists only the views a sport has', () => {
    expect(shellNav('/nba/model', false).views.map(view => view.label)).toEqual(['Slate', 'Props', 'Model'])
    expect(shellNav('/nba/board', false).views.filter(view => view.active).map(view => view.view)).toEqual(['props'])
  })

  it('keeps the sport but no view on a detail page', () => {
    const game = shellNav('/nfl/game/52', false)
    expect(active(game.sports).map(sport => sport.code)).toEqual(['nfl'])
    expect(game.views).toHaveLength(3)
    expect(active(game.views)).toEqual([])
    expect(active(shellNav('/tennis/match/82864', false).sports).map(sport => sport.code)).toEqual(['tennis'])
  })

  it('shows no views off the sport pages', () => {
    for (const path of ['/how-it-works', '/admin', '/parlays']) {
      const nav = shellNav(path, true)
      expect(nav.views).toEqual([])
      expect(active(nav.sports)).toEqual([])
    }
    expect(active(shellNav('/how-it-works', false).links).map(link => link.key)).toEqual(['/how-it-works'])
  })

  it('hides Admin from visitors and shows it to the owner', () => {
    expect(shellNav('/', false).links.map(link => link.label)).toEqual(['How it works'])
    expect(shellNav('/', true).links.map(link => link.label)).toEqual(['How it works', 'Admin'])
  })
})

describe('documentTitle', () => {
  it('names each sport view', () => {
    expect(documentTitle('/')).toBe('Tennis slate · Lineform')
    expect(documentTitle('/tennis/board')).toBe('Tennis props · Lineform')
    expect(documentTitle('/nfl')).toBe('NFL slate · Lineform')
    expect(documentTitle('/nfl/model')).toBe('NFL model · Lineform')
    expect(documentTitle('/nba/model')).toBe('NBA model · Lineform')
  })

  it('names detail pages by kind', () => {
    expect(documentTitle('/nfl/game/52')).toBe('NFL game · Lineform')
    expect(documentTitle('/nba/game/21320')).toBe('NBA game · Lineform')
    expect(documentTitle('/tennis/match/82864')).toBe('Tennis match · Lineform')
    expect(documentTitle('/tennis/player/7')).toBe('Tennis player · Lineform')
  })

  it('names the other pages and falls back to the app name', () => {
    expect(documentTitle('/how-it-works')).toBe('How it works · Lineform')
    expect(documentTitle('/admin')).toBe('Admin · Lineform')
    expect(documentTitle('/parlays')).toBe('Lineform')
    expect(documentTitle('/nope')).toBe('Lineform')
  })
})

describe('menuSections', () => {
  it('nests each sport\'s views under it, then the other links', () => {
    expect(menuSections(false)).toEqual([
      { label: 'Tennis', items: [{ key: '/', label: 'Slate' }, { key: '/tennis/board', label: 'Props' }, { key: '/tennis/model', label: 'Model' }] },
      { label: 'NFL', items: [{ key: '/nfl', label: 'Slate' }, { key: '/nfl/board', label: 'Props' }, { key: '/nfl/model', label: 'Model' }] },
      { label: 'NBA', items: [{ key: '/nba', label: 'Slate' }, { key: '/nba/board', label: 'Props' }, { key: '/nba/model', label: 'Model' }] },
      { label: null, items: [{ key: '/how-it-works', label: 'How it works' }] },
    ])
  })

  it('adds Admin for the owner', () => {
    expect(menuSections(true).at(-1)?.items.map(item => item.label)).toEqual(['How it works', 'Admin'])
  })
})
