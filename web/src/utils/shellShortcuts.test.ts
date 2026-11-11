import { describe, expect, it } from 'vitest'
import { shellShortcutTarget } from '~/utils/shellShortcuts'
import { shellNav } from '~/utils/sportNav'

const press = (key: string, mods: Partial<{ ctrlKey: boolean, metaKey: boolean, altKey: boolean }> = {}) =>
  ({ key, ctrlKey: false, metaKey: false, altKey: false, ...mods })

describe('shellShortcutTarget', () => {
  const nflProps = shellNav('/nfl/props', false)

  it('switches sport by number and keeps the view', () => {
    expect(shellShortcutTarget(press('1'), nflProps)).toBe('/tennis/props')
    expect(shellShortcutTarget(press('3'), nflProps)).toBe('/nba/props')
    expect(shellShortcutTarget(press('4'), nflProps)).toBe('/nhl/props')
    expect(shellShortcutTarget(press('5'), nflProps)).toBeNull()
  })

  it('does nothing for the sport already open, and keeps the view from its game pages', () => {
    expect(shellShortcutTarget(press('2'), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('2'), shellNav('/nfl/model', false))).toBeNull()
    expect(shellShortcutTarget(press('2'), shellNav('/nfl/game/52', false, 'props'))).toBe('/nfl/props')
    expect(shellShortcutTarget(press('0'), nflProps)).toBeNull()
  })

  it('cycles sports with brackets, wrapping at both ends', () => {
    expect(shellShortcutTarget(press(']'), nflProps)).toBe('/nba/props')
    expect(shellShortcutTarget(press('['), nflProps)).toBe('/tennis/props')
    expect(shellShortcutTarget(press('['), shellNav('/tennis/model', false))).toBe('/nhl/model')
    expect(shellShortcutTarget(press(']'), shellNav('/nhl', false))).toBe('/tennis')
  })

  it('has no sport to cycle from outside a sport', () => {
    expect(shellShortcutTarget(press(']'), shellNav('/', false))).toBeNull()
  })

  it('switches view within the current sport, either case, and ignores the view already open', () => {
    expect(shellShortcutTarget(press('s'), nflProps)).toBe('/nfl')
    expect(shellShortcutTarget(press('M'), nflProps)).toBe('/nfl/model')
    expect(shellShortcutTarget(press('p'), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('p'), shellNav('/nba/game/7', false))).toBe('/nba/props')
  })

  it('has no view to open on Home', () => {
    expect(shellShortcutTarget(press('p'), shellNav('/', false))).toBeNull()
    expect(shellShortcutTarget(press('2', {}), shellNav('/', false, 'props'))).toBe('/nfl/props')
  })

  it('leaves browser shortcuts and unrelated keys alone', () => {
    expect(shellShortcutTarget(press('1', { ctrlKey: true }), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('p', { metaKey: true }), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('s', { altKey: true }), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('x'), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('Enter'), nflProps)).toBeNull()
    expect(shellShortcutTarget(press('?'), nflProps)).toBeNull()
  })
})
