import { describe, expect, it } from 'vitest'
import { shouldViewTransition, viewTransitionsSupported, type ViewTransitionInput } from '~/utils/viewTransition'

const base: ViewTransitionInput = { from: '/nfl', to: '/nfl/game/12', navigationType: 'PUSH', supported: true, reducedMotion: false }

describe('shouldViewTransition', () => {
  it.each([
    ['slate to game', '/nfl', '/nfl/game/12'],
    ['game to player', '/nba/game/7', '/nba/player/3'],
    ['slate to props', '/nhl', '/nhl/props'],
    ['across sports', '/tennis', '/nfl/model'],
  ])('crossfades %s', (_label, from, to) => {
    expect(shouldViewTransition({ ...base, from, to })).toBe(true)
  })

  it('crossfades a replace navigation', () => {
    expect(shouldViewTransition({ ...base, navigationType: 'REPLACE' })).toBe(true)
  })

  it('skips when the browser lacks the API', () => {
    expect(shouldViewTransition({ ...base, supported: false })).toBe(false)
  })

  it('skips under reduced motion', () => {
    expect(shouldViewTransition({ ...base, reducedMotion: true })).toBe(false)
  })

  it('skips Back and Forward', () => {
    expect(shouldViewTransition({ ...base, navigationType: 'POP' })).toBe(false)
  })

  it('skips a change that keeps the path, such as a filter in the query string', () => {
    expect(shouldViewTransition({ ...base, from: '/nfl', to: '/nfl' })).toBe(false)
  })

  it.each([
    ['from home', '/', '/nfl'],
    ['to tools', '/nfl', '/tools'],
    ['to a path outside every sport', '/nba', '/how-it-works'],
  ])('skips a trip %s', (_label, from, to) => {
    expect(shouldViewTransition({ ...base, from, to })).toBe(false)
  })
})

describe('viewTransitionsSupported', () => {
  it('reads whether startViewTransition is a function', () => {
    const doc = { startViewTransition: () => ({}) } as unknown as Pick<Document, 'startViewTransition'>
    expect(viewTransitionsSupported(doc)).toBe(true)
    expect(viewTransitionsSupported({} as Pick<Document, 'startViewTransition'>)).toBe(false)
    expect(viewTransitionsSupported(undefined)).toBe(false)
  })
})
