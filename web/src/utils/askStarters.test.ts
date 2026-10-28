import { describe, expect, it } from 'vitest'
import { askErrorMessage } from '~/utils/askError'
import { askStarters } from '~/utils/askStarters'

describe('askStarters', () => {
  it.each(['nba', 'nfl', 'tennis'] as const)('offers three %s questions', sport => {
    const starters = askStarters(sport)
    expect(starters).toHaveLength(3)
    expect(starters).not.toEqual(askStarters(null))
  })

  it('uses the general set off a sport page and on NHL, which Ask does not cover', () => {
    expect(askStarters(null)).toHaveLength(3)
    expect(askStarters('nhl')).toEqual(askStarters(null))
  })
})

describe('askErrorMessage', () => {
  it.each([
    [429, /faster than Lineform allows/],
    [404, /off right now/],
    [503, /off right now/],
    [422, /500 characters/],
    [null, /Couldn't reach Lineform/],
    [500, /Something went wrong/],
  ] as const)('explains %s', (status, copy) => {
    expect(askErrorMessage(status)).toMatch(copy)
  })
})
