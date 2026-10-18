import { describe, expect, it } from 'vitest'
import { detailTitleReducer, resolveDocumentTitle, type DetailTitleRegistration } from '~/utils/documentTitle'

const DETAILS = [
  ['/nfl/game/91', 'BUF @ LV', 'NFL game'],
  ['/nba/game/21319', 'PHI @ NY', 'NBA game'],
  ['/tennis/match/88732', 'Katarzyna Kawa vs Daria Snigur', 'Tennis match'],
  ['/nfl/player/40399', 'Ashton Jeanty', 'NFL player'],
  ['/tennis/player/2415', 'Katarzyna Kawa', 'Tennis player'],
]

function registration(pathname = '/nba/game/21319', label: string | null = 'PHI @ NY', owner = 'current'): DetailTitleRegistration {
  return { pathname, label, owner }
}

describe('resolveDocumentTitle', () => {
  it.each(DETAILS)('names the loaded entity on %s', (pathname, label, kind) => {
    expect(resolveDocumentTitle(pathname, registration(pathname, label))).toBe(`${label} - ${kind} · Lineform`)
  })

  it.each(DETAILS)('keeps the generic title while %s is unavailable', (pathname, _label, kind) => {
    expect(resolveDocumentTitle(pathname, null)).toBe(`${kind} · Lineform`)
    expect(resolveDocumentTitle(pathname, registration(pathname, null))).toBe(`${kind} · Lineform`)
  })

  it.each([null, '', '   '])('ignores an empty entity label: %s', label => {
    expect(resolveDocumentTitle('/nba/game/21319', registration('/nba/game/21319', label))).toBe('NBA game · Lineform')
  })

  it.each([
    ['/nba/game/21320', 'NBA game · Lineform'],
    ['/nfl/player/40399', 'NFL player · Lineform'],
    ['/nba', 'NBA slate · Lineform'],
    ['/', 'Tennis slate · Lineform'],
  ])('ignores the old game label after navigating to %s', (pathname, expected) => {
    expect(resolveDocumentTitle(pathname, registration())).toBe(expected)
  })

  it('trims a loaded label without changing the entity text', () => {
    expect(resolveDocumentTitle('/nba/game/21319', registration('/nba/game/21319', ' PHI @ NY '))).toBe('PHI @ NY - NBA game · Lineform')
  })
})

describe('detailTitleReducer', () => {
  it('registers loaded metadata and then clears it when that owner leaves', () => {
    const state = detailTitleReducer(null, { type: 'register', registration: registration() })
    expect(resolveDocumentTitle('/nba/game/21319', state)).toBe('PHI @ NY - NBA game · Lineform')
    const cleared = detailTitleReducer(state, { type: 'clear', owner: 'current' })
    expect(resolveDocumentTitle('/nba/game/21319', cleared)).toBe('NBA game · Lineform')
  })

  it('does not let an older page cleanup erase a newer registration', () => {
    const current = registration('/nfl/player/40399', 'Ashton Jeanty', 'new-page')
    const state = detailTitleReducer(current, { type: 'clear', owner: 'old-page' })
    expect(resolveDocumentTitle('/nfl/player/40399', state)).toBe('Ashton Jeanty - NFL player · Lineform')
  })

  it('replaces a loaded label with generic metadata after a failed request', () => {
    const state = detailTitleReducer(registration(), { type: 'register', registration: registration('/nba/game/21319', null) })
    expect(resolveDocumentTitle('/nba/game/21319', state)).toBe('NBA game · Lineform')
  })

  it('handles cleanup before any page has registered', () => {
    expect(detailTitleReducer(null, { type: 'clear', owner: 'old-page' })).toBeNull()
  })
})
