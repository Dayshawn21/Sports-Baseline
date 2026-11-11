import { describe, expect, it } from 'vitest'
import { boardViewSearch, DEFAULT_BOARD_VIEW, gameViewSearch, parseBoardView, parseGameView } from '~/utils/nflViewParams'

const parse = (query: string) => parseBoardView(new URLSearchParams(query))

describe('board view params', () => {
  it('round trips a full view', () => {
    const view = { season: 2026, week: 9, position: 'WR' as const, market: 'receptions', game: '121', showAll: true, q: 'aj brown', team: 'KC' }

    expect(parse(boardViewSearch(view).toString())).toEqual(view)
  })

  it('leaves a blank search and all teams out of the URL', () => {
    expect(boardViewSearch({ ...DEFAULT_BOARD_VIEW, q: '  ', team: 'all' }).toString()).toBe('')
  })

  it('omits every default', () => {
    expect(boardViewSearch(DEFAULT_BOARD_VIEW).toString()).toBe('')
    expect(boardViewSearch({ ...DEFAULT_BOARD_VIEW, position: 'TE' }).toString()).toBe('position=TE')
  })

  it('reads an empty query as the default view', () => {
    expect(parse('')).toEqual(DEFAULT_BOARD_VIEW)
  })

  it('falls back per field on bad values', () => {
    expect(parse('week=abc&season=2026').week).toBeNull()
    expect(parse('position=zz').position).toBe('all')
    expect(parse('market=Bad Market!').market).toBeNull()
    expect(parse('game=abc').game).toBe('all')
    expect(parse('all=yes').showAll).toBe(false)
  })

  it('pins the week only when season and week are both valid', () => {
    expect(parse('season=2026').season).toBeNull()
    expect(parse('week=9').week).toBeNull()
    expect(parse('season=2026&week=99')).toMatchObject({ season: null, week: null })
    expect(parse('season=2026&week=9')).toMatchObject({ season: 2026, week: 9 })
  })

  it('distinguishes game=all from a numeric game', () => {
    expect(parse('game=all').game).toBe('all')
    expect(parse('game=121').game).toBe('121')
  })
})

describe('game view params', () => {
  it('round trips and omits defaults', () => {
    expect(gameViewSearch({ position: 'all', showAll: false }).toString()).toBe('')
    expect(parseGameView(new URLSearchParams(gameViewSearch({ position: 'RB', showAll: true }).toString()))).toEqual({ position: 'RB', showAll: true })
  })

  it('ignores an unknown position', () => {
    expect(parseGameView(new URLSearchParams('position=zz'))).toEqual({ position: 'all', showAll: false })
  })
})
