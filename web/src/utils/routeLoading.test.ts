import { describe, expect, it } from 'vitest'
import { routeLoadingShape } from './routeLoading'

describe('routeLoadingShape', () => {
  it('uses the slate skeleton on every sport slate', () => {
    for (const path of ['/tennis', '/nfl', '/nba', '/nhl']) expect(routeLoadingShape(path)).toBe('slate')
  })

  it('uses the board skeleton on every prop board', () => {
    for (const path of ['/tennis/props', '/nfl/props', '/nba/props', '/nhl/props']) expect(routeLoadingShape(path)).toBe('board')
  })

  it('keeps the spinner on detail and model pages', () => {
    expect(routeLoadingShape('/nfl/game/137')).toBe('spinner')
    expect(routeLoadingShape('/nba/player/2544')).toBe('spinner')
    expect(routeLoadingShape('/tennis/model')).toBe('spinner')
  })

  it('keeps the spinner outside the sports', () => {
    expect(routeLoadingShape('/')).toBe('spinner')
    expect(routeLoadingShape('/tools')).toBe('spinner')
    expect(routeLoadingShape('/no-such-page')).toBe('spinner')
  })
})
