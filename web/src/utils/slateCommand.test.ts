import { describe, expect, it } from 'vitest'
import type { SlateCommandRowInput, SlateCommandScope } from '~/types/slateCommand'
import {
  firstSlateCommandPath,
  initialSlateCommandState,
  matchingSlateCommandRows,
  matchingSlateCommandTargets,
  nbaSlateCommandRows,
  nflSlateCommandRows,
  normalizeSlateCommand,
  slateCommandReducer,
  slateCommandRow,
  tennisSlateCommandRows,
} from '~/utils/slateCommand'

function row(input: Partial<SlateCommandRowInput> = {}) {
  return slateCommandRow({
    key: 'hou-jax',
    path: '/nfl/game/7',
    searchTerms: ['HOU at JAX', 'Houston Texans', 'Jacksonville Jaguars'],
    targets: [
      { key: 'game-7', kind: 'game', label: 'HOU at JAX', context: 'NFL game', path: '/nfl/game/7' },
      { key: 'team-hou', kind: 'team', label: 'HOU', context: 'Houston Texans', path: '/nfl/game/7' },
      { key: 'player-22', kind: 'player', label: 'Nico Collins', context: 'HOU at JAX', path: '/nfl/player/22' },
    ],
    ...input,
  })
}

describe('normalizeSlateCommand', () => {
  it('trims, collapses whitespace, and ignores case', () => {
    expect(normalizeSlateCommand('  Nico   COLLINS\n')).toBe('nico collins')
  })
})

describe('slateCommandRow', () => {
  it('de-duplicates targets by stable key without changing first-seen order', () => {
    const duplicate = { key: 'player-22', kind: 'player' as const, label: 'Nico Collins', context: 'duplicate', path: '/nfl/player/22' }
    const built = row({ targets: [...row().targets, duplicate] })
    expect(built.targets.map(target => target.key)).toEqual(['game-7', 'team-hou', 'player-22'])
    expect(built.targets[2].context).toBe('HOU at JAX')
    expect(built.targets.every(target => target.parentPath === '/nfl/game/7')).toBe(true)
  })
})

describe('tennisSlateCommandRows', () => {
  const tennisRows = tennisSlateCommandRows([
    {
      key: 'm-41',
      tournament: 'Indian Wells',
      tour: 'CHALLENGER',
      tourLabel: 'WTA 125',
      players: ['Coco Gauff', 'Iga Swiatek'],
      match: {
        matchId: 41,
        prediction: { p1Id: 7, p2Id: 8 },
        props: [
          { playerId: 7, playerName: 'Coco Gauff' },
          { playerId: 7, playerName: 'C. Gauff' },
          { playerId: null, playerName: 'Unlinked Player' },
        ],
      },
    },
    {
      key: 'unlinked',
      tournament: null,
      tour: null,
      tourLabel: null,
      players: ['Unknown', null],
      match: { matchId: null, prediction: null, props: [{ playerId: -2, playerName: 'Unknown' }] },
    },
  ])

  it('builds a match-first target list and de-duplicates valid player destinations', () => {
    expect(tennisRows).toHaveLength(1)
    expect(tennisRows[0].targets.map(target => [target.kind, target.path])).toEqual([
      ['match', '/tennis/match/41'],
      ['player', '/tennis/player/7'],
      ['player', '/tennis/player/8'],
    ])
  })

  it('matches matchup, tournament, tour, and player aliases without changing the parent path', () => {
    for (const query of ['Gauff Swiatek', 'Indian Wells', 'challenger', 'WTA 125', 'C. Gauff']) {
      expect(firstSlateCommandPath(tennisRows, query)).toBe('/tennis/match/41')
    }
    expect(matchingSlateCommandTargets(tennisRows, 'C. Gauff').map(target => target.path)).toEqual([
      '/tennis/match/41',
      '/tennis/player/7',
    ])
  })

  it('omits rows and player targets whose IDs cannot form valid routes', () => {
    expect(tennisRows.some(item => item.key === 'unlinked')).toBe(false)
    expect(tennisRows[0].targets.some(target => target.label === 'Unlinked Player')).toBe(false)
  })
})

describe('nflSlateCommandRows', () => {
  const rows = nflSlateCommandRows([
    {
      gameId: 71,
      awayTeam: 'HOU',
      homeTeam: 'JAX',
      lines: [
        { playerId: 22, playerName: 'Nico Collins' },
        { playerId: 22, playerName: 'N. Collins' },
        { playerId: 0, playerName: 'Invalid Player' },
      ],
    },
    { gameId: -1, awayTeam: 'BAD', homeTeam: 'ID', lines: [] },
  ])

  it('builds game, team, and de-duplicated valid player targets', () => {
    expect(rows).toHaveLength(1)
    expect(rows[0].targets.map(target => [target.kind, target.path])).toEqual([
      ['game', '/nfl/game/71'],
      ['team', '/nfl/game/71'],
      ['team', '/nfl/game/71'],
      ['player', '/nfl/player/22'],
    ])
  })

  it('matches team and player aliases while Enter keeps the parent game destination', () => {
    expect(matchingSlateCommandTargets(rows, 'JAX').map(target => target.kind)).toEqual(['game', 'team'])
    expect(matchingSlateCommandTargets(rows, 'N. Collins').map(target => target.kind)).toEqual(['game', 'player'])
    expect(firstSlateCommandPath(rows, 'Nico')).toBe('/nfl/game/71')
  })
})

describe('nbaSlateCommandRows', () => {
  const games = [{
    gameId: 81,
    awayTeam: 'OKC',
    homeTeam: 'MIN',
    awayTeamName: 'Oklahoma City Thunder',
    homeTeamName: 'Minnesota Timberwolves',
  }]
  const gaps = [
    { gameId: 81, playerId: 31, playerName: 'Shai Gilgeous-Alexander' },
    { gameId: 81, playerId: 31, playerName: 'Shai Gilgeous Alexander' },
    { gameId: 81, playerId: -1, playerName: 'Invalid Player' },
    { gameId: 999, playerId: 32, playerName: 'Other Game' },
  ]

  it('matches team codes, full names, and de-duplicated digest players to the game route', () => {
    const rows = nbaSlateCommandRows(games, gaps)
    for (const query of ['OKC', 'Oklahoma City', 'Timberwolves', 'Gilgeous Alexander']) {
      expect(firstSlateCommandPath(rows, query)).toBe('/nba/game/81')
    }
    expect(rows[0].targets.filter(target => target.kind === 'player').map(target => target.path)).toEqual(['/nba/game/81'])
    expect(matchingSlateCommandTargets(rows, 'Shai').map(target => target.kind)).toEqual(['game', 'player'])
  })

  it('keeps game and team search available without digest data', () => {
    const rows = nbaSlateCommandRows(games, [])
    expect(matchingSlateCommandTargets(rows, 'Minnesota').map(target => target.kind)).toEqual(['game', 'team'])
    expect(matchingSlateCommandTargets(rows, 'Shai')).toEqual([])
  })
})

describe('command matching', () => {
  const rows = [
    row(),
    row({
      key: 'buf-lv',
      path: '/nfl/game/8',
      searchTerms: ['BUF at LV'],
      targets: [{ key: 'game-8', kind: 'game', label: 'BUF at LV', context: 'NFL game', path: '/nfl/game/8' }],
    }),
  ]

  it('requires every query token while preserving registered row order', () => {
    expect(matchingSlateCommandRows(rows, 'jax hou').map(item => item.key)).toEqual(['hou-jax'])
    expect(matchingSlateCommandRows(rows, 'at').map(item => item.key)).toEqual(['hou-jax', 'buf-lv'])
  })

  it('lets a player match its parent game and returns the direct player target', () => {
    expect(matchingSlateCommandRows(rows, 'nico').map(item => item.key)).toEqual(['hou-jax'])
    expect(matchingSlateCommandTargets(rows, 'nico').map(target => target.path)).toEqual(['/nfl/player/22'])
    expect(firstSlateCommandPath(rows, 'nico')).toBe('/nfl/game/7')
  })

  it('treats an empty query as no filter and no open results', () => {
    expect(matchingSlateCommandRows(rows, '  ')).toEqual(rows)
    expect(matchingSlateCommandTargets(rows, '')).toEqual([])
    expect(firstSlateCommandPath(rows, 'missing')).toBeNull()
  })
})

describe('slateCommandReducer', () => {
  const scope = (periodKey: string): SlateCommandScope => ({ periodKey, rows: [row()] })

  it('keeps a query when the same period refreshes its registered rows', () => {
    let state = slateCommandReducer(initialSlateCommandState('/nfl'), { type: 'register', routeKey: '/nfl', scope: scope('2026-6') })
    state = slateCommandReducer(state, { type: 'query', query: 'JAX' })
    state = slateCommandReducer(state, { type: 'register', routeKey: '/nfl', scope: scope('2026-6') })
    expect(state.query).toBe('JAX')
  })

  it('returns the same state for an unchanged scope registration', () => {
    const registered = scope('2026-6')
    const state = { routeKey: '/nfl', query: '', scope: registered }
    expect(slateCommandReducer(state, { type: 'register', routeKey: '/nfl', scope: registered })).toBe(state)
    expect(slateCommandReducer(state, { type: 'register', routeKey: '/nfl', scope: scope('2026-6') })).toBe(state)
  })

  it('clears stale query and targets when the route changes', () => {
    const active = { routeKey: '/nfl', query: 'JAX', scope: scope('2026-6') }
    expect(slateCommandReducer(active, { type: 'route', routeKey: '/nba' })).toEqual(initialSlateCommandState('/nba'))
  })

  it('clears a stale query when the registered period changes or disappears', () => {
    const active = { routeKey: '/nfl', query: 'JAX', scope: scope('2026-6') }
    expect(slateCommandReducer(active, { type: 'register', routeKey: '/nfl', scope: scope('2026-7') }).query).toBe('')
    expect(slateCommandReducer(active, { type: 'register', routeKey: '/nfl', scope: null })).toMatchObject({ query: '', scope: null })
  })
})
