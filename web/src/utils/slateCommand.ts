import type {
  SlateCommandRow,
  SlateCommandRowInput,
  SlateCommandScope,
  SlateCommandTarget,
  SlateCommandTargetInput,
} from '~/types/slateCommand'

export interface SlateCommandState {
  routeKey: string
  query: string
  scope: SlateCommandScope | null
}

interface TennisCommandPrediction {
  p1Id?: number | null
  p2Id?: number | null
}

interface TennisCommandProp {
  playerId: number | null
  playerName?: string | null
}

interface TennisCommandRowInput {
  key: string
  tournament: string | null
  tour: string | null
  tourLabel: string | null
  players: readonly [string, string | null]
  match: {
    matchId: number | null
    prediction: TennisCommandPrediction | null
    props: readonly TennisCommandProp[]
  }
}

interface NflCommandGameInput {
  gameId: number
  awayTeam: string
  homeTeam: string
  lines: readonly { playerId: number, playerName: string }[]
}

interface NbaCommandGameInput {
  gameId: number
  awayTeam: string
  homeTeam: string
  awayTeamName: string
  homeTeamName: string
}

interface NbaCommandGapInput {
  gameId: number
  playerId: number
  playerName: string
}

export type SlateCommandAction =
  | { type: 'route'; routeKey: string }
  | { type: 'register'; routeKey: string; scope: SlateCommandScope | null }
  | { type: 'query'; query: string }
  | { type: 'clear' }

export function normalizeSlateCommand(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLowerCase()
}

function searchText(values: readonly string[]): string {
  return normalizeSlateCommand(values.filter(Boolean).join(' '))
}

function targetOf(input: SlateCommandTargetInput, parentPath: string): SlateCommandTarget {
  return {
    key: input.key,
    kind: input.kind,
    label: input.label,
    context: input.context,
    path: input.path,
    parentPath,
    searchText: searchText([input.label, ...(input.searchTerms ?? [])]),
  }
}

/** Build one immutable row and keep only the first target for each stable key. */
export function slateCommandRow(input: SlateCommandRowInput): SlateCommandRow {
  const seen = new Set<string>()
  const targets = input.targets.flatMap(target => {
    if (seen.has(target.key)) return []
    seen.add(target.key)
    return [targetOf(target, input.path)]
  })
  return {
    key: input.key,
    path: input.path,
    searchText: searchText([...input.searchTerms, ...targets.map(target => target.searchText)]),
    targets,
  }
}

function validId(value: number | null | undefined): value is number {
  return Number.isInteger(value) && Number(value) > 0
}

/** Map loaded Tennis slate rows into command rows without inventing destinations for missing IDs. */
export function tennisSlateCommandRows(rows: readonly TennisCommandRowInput[]): SlateCommandRow[] {
  return rows.flatMap(row => {
    const matchId = row.match.matchId
    if (!validId(matchId)) return []

    const matchPath = `/tennis/match/${matchId}`
    const matchup = row.players[1] ? `${row.players[0]} vs ${row.players[1]}` : row.players[0]
    const rowTerms = [
      ...row.players.filter((name): name is string => Boolean(name)),
      row.tournament ?? '',
      row.tour ?? '',
      row.tourLabel ?? '',
    ]
    const players = new Map<number, { label: string, aliases: string[] }>()

    function addPlayer(playerId: number | null | undefined, name: string | null | undefined) {
      if (!validId(playerId) || !name) return
      const existing = players.get(playerId)
      if (existing) {
        if (!existing.aliases.includes(name)) existing.aliases.push(name)
      } else {
        players.set(playerId, { label: name, aliases: [name] })
      }
    }

    addPlayer(row.match.prediction?.p1Id, row.players[0])
    addPlayer(row.match.prediction?.p2Id, row.players[1])
    for (const prop of row.match.props) addPlayer(prop.playerId, prop.playerName)
    const targetTerms = [...rowTerms, ...[...players.values()].flatMap(player => player.aliases)]

    return [slateCommandRow({
      key: row.key,
      path: matchPath,
      searchTerms: targetTerms,
      targets: [
        {
          key: `match-${matchId}`,
          kind: 'match',
          label: matchup,
          context: row.tournament ?? row.tourLabel ?? row.tour ?? 'Tennis match',
          path: matchPath,
          searchTerms: targetTerms,
        },
        ...[...players].map(([playerId, player]) => ({
          key: `player-${playerId}`,
          kind: 'player' as const,
          label: player.label,
          context: matchup,
          path: `/tennis/player/${playerId}`,
          searchTerms: player.aliases,
        })),
      ],
    })]
  })
}

/** Build NFL game, team, and loaded prop-player targets in displayed game order. */
export function nflSlateCommandRows(games: readonly NflCommandGameInput[]): SlateCommandRow[] {
  return games.flatMap(game => {
    if (!validId(game.gameId)) return []
    const path = `/nfl/game/${game.gameId}`
    const matchup = `${game.awayTeam} @ ${game.homeTeam}`
    const players = new Map<number, { label: string, aliases: string[] }>()
    for (const line of game.lines) {
      if (!validId(line.playerId) || !line.playerName) continue
      const existing = players.get(line.playerId)
      if (existing) {
        if (!existing.aliases.includes(line.playerName)) existing.aliases.push(line.playerName)
      } else {
        players.set(line.playerId, { label: line.playerName, aliases: [line.playerName] })
      }
    }
    const terms = [game.awayTeam, game.homeTeam, ...[...players.values()].flatMap(player => player.aliases)]
    return [slateCommandRow({
      key: `nfl-${game.gameId}`,
      path,
      searchTerms: terms,
      targets: [
        { key: `game-${game.gameId}`, kind: 'game', label: matchup, context: 'NFL game', path, searchTerms: terms },
        { key: `away-${game.awayTeam}`, kind: 'team', label: game.awayTeam, context: matchup, path },
        { key: `home-${game.homeTeam}`, kind: 'team', label: game.homeTeam, context: matchup, path },
        ...[...players].map(([playerId, player]) => ({
          key: `player-${playerId}`,
          kind: 'player' as const,
          label: player.label,
          context: matchup,
          path: `/nfl/player/${playerId}`,
          searchTerms: player.aliases,
        })),
      ],
    })]
  })
}

/** Build NBA game/team targets plus only the digest players already loaded for each game. */
export function nbaSlateCommandRows(
  games: readonly NbaCommandGameInput[],
  gaps: readonly NbaCommandGapInput[],
): SlateCommandRow[] {
  const gapsByGame = new Map<number, NbaCommandGapInput[]>()
  for (const gap of gaps) {
    const group = gapsByGame.get(gap.gameId)
    if (group) group.push(gap)
    else gapsByGame.set(gap.gameId, [gap])
  }

  return games.flatMap(game => {
    if (!validId(game.gameId)) return []
    const path = `/nba/game/${game.gameId}`
    const matchup = `${game.awayTeam} @ ${game.homeTeam}`
    const players = new Map<number, { label: string, aliases: string[] }>()
    for (const gap of gapsByGame.get(game.gameId) ?? []) {
      if (!validId(gap.playerId) || !gap.playerName) continue
      const existing = players.get(gap.playerId)
      if (existing) {
        if (!existing.aliases.includes(gap.playerName)) existing.aliases.push(gap.playerName)
      } else {
        players.set(gap.playerId, { label: gap.playerName, aliases: [gap.playerName] })
      }
    }
    const teamTerms = [game.awayTeam, game.homeTeam, game.awayTeamName, game.homeTeamName]
    const terms = [...teamTerms, ...[...players.values()].flatMap(player => player.aliases)]
    return [slateCommandRow({
      key: `nba-${game.gameId}`,
      path,
      searchTerms: terms,
      targets: [
        { key: `game-${game.gameId}`, kind: 'game', label: matchup, context: 'NBA game', path, searchTerms: terms },
        { key: `away-${game.awayTeam}`, kind: 'team', label: game.awayTeam, context: game.awayTeamName, path, searchTerms: [game.awayTeamName] },
        { key: `home-${game.homeTeam}`, kind: 'team', label: game.homeTeam, context: game.homeTeamName, path, searchTerms: [game.homeTeamName] },
        ...[...players].map(([playerId, player]) => ({
          key: `player-${playerId}`,
          kind: 'player' as const,
          label: player.label,
          context: matchup,
          path,
          searchTerms: player.aliases,
        })),
      ],
    })]
  })
}

function tokens(query: string): string[] {
  const normalized = normalizeSlateCommand(query)
  return normalized ? normalized.split(' ') : []
}

function includesEveryToken(value: string, queryTokens: readonly string[]): boolean {
  return queryTokens.every(token => value.includes(token))
}

/** Filter without sorting, so the slate's existing row order remains authoritative. */
export function matchingSlateCommandRows(rows: readonly SlateCommandRow[], query: string): SlateCommandRow[] {
  const queryTokens = tokens(query)
  if (queryTokens.length === 0) return [...rows]
  return rows.filter(row => includesEveryToken(row.searchText, queryTokens))
}

/** Return matching jump targets in row order; a row-only match falls back to its first target. */
export function matchingSlateCommandTargets(rows: readonly SlateCommandRow[], query: string): SlateCommandTarget[] {
  const queryTokens = tokens(query)
  if (queryTokens.length === 0) return []
  return matchingSlateCommandRows(rows, query).flatMap(row => {
    const direct = row.targets.filter(target => includesEveryToken(target.searchText, queryTokens))
    return direct.length > 0 ? direct : row.targets.slice(0, 1)
  })
}

export function firstSlateCommandPath(rows: readonly SlateCommandRow[], query: string): string | null {
  return matchingSlateCommandRows(rows, query)[0]?.path ?? null
}

export function initialSlateCommandState(routeKey: string): SlateCommandState {
  return { routeKey, query: '', scope: null }
}

function sameScope(left: SlateCommandScope | null, right: SlateCommandScope | null): boolean {
  if (left === right) return true
  if (!left || !right || left.periodKey !== right.periodKey || left.rows.length !== right.rows.length) return false
  return left.rows.every((row, rowIndex) => {
    const other = right.rows[rowIndex]
    return row.key === other.key
      && row.path === other.path
      && row.searchText === other.searchText
      && row.targets.length === other.targets.length
      && row.targets.every((target, targetIndex) => {
        const otherTarget = other.targets[targetIndex]
        return target.key === otherTarget.key
          && target.kind === otherTarget.kind
          && target.label === otherTarget.label
          && target.context === otherTarget.context
          && target.path === otherTarget.path
          && target.parentPath === otherTarget.parentPath
          && target.searchText === otherTarget.searchText
      })
  })
}

/** Route and period changes invalidate both the query and its page-owned target set. */
export function slateCommandReducer(state: SlateCommandState, action: SlateCommandAction): SlateCommandState {
  if (action.type === 'route') {
    return action.routeKey === state.routeKey ? state : initialSlateCommandState(action.routeKey)
  }
  if (action.type === 'register') {
    if (action.routeKey === state.routeKey && sameScope(action.scope, state.scope)) return state
    const samePeriod = action.routeKey === state.routeKey
      && action.scope !== null
      && action.scope.periodKey === state.scope?.periodKey
    return {
      routeKey: action.routeKey,
      query: samePeriod ? state.query : '',
      scope: action.scope,
    }
  }
  if (action.type === 'query') return { ...state, query: action.query }
  return state.query ? { ...state, query: '' } : state
}
