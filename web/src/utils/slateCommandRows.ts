/** Each sport page's slate search rows; kept apart from `slateCommand` so the shell's search field loads without them. */
import type { SlateCommandRow, SlateCommandRowInput, SlateCommandTarget, SlateCommandTargetInput } from '~/types/slateCommand'
import { nflTeamName } from '~/utils/nflTeams'
import { normalizeSlateCommand } from '~/utils/slateCommand'
import { type MatchupSide, slateMatchup } from '~/utils/slateMatchup'

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
  /** The game result's second line: its start time or final score (`commandGameContext`). */
  commandContext?: string
}

interface TeamCommandGameInput {
  gameId: number
  awayTeam: string
  homeTeam: string
  awayTeamName: string
  homeTeamName: string
  commandContext?: string
}


/** A game result's context: its start or state ("Mon 7:15 PM CT", "Result pending"), with the score once final. */
export function commandGameContext(label: string, final?: { away: MatchupSide, home: MatchupSide }): string {
  if (!final || final.away.score === null || final.home.score === null) return label
  return `${label} · ${slateMatchup(final.away, final.home)}`
}

interface NbaCommandGapInput {
  gameId: number
  playerId: number
  playerName: string
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
          searchTerms: rowTerms,
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
    const awayName = nflTeamName(game.awayTeam)
    const homeName = nflTeamName(game.homeTeam)
    const teamTerms = [game.awayTeam, game.homeTeam, awayName ?? '', homeName ?? '']
    const terms = [...teamTerms, ...[...players.values()].flatMap(player => player.aliases)]
    return [slateCommandRow({
      key: `nfl-${game.gameId}`,
      path,
      searchTerms: terms,
      targets: [
        { key: `game-${game.gameId}`, kind: 'game', label: matchup, context: game.commandContext ?? 'NFL game', path, searchTerms: teamTerms },
        { key: `away-${game.awayTeam}`, kind: 'team', label: game.awayTeam, context: awayName ?? matchup, path, searchTerms: awayName ? [awayName] : [] },
        { key: `home-${game.homeTeam}`, kind: 'team', label: game.homeTeam, context: homeName ?? matchup, path, searchTerms: homeName ? [homeName] : [] },
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
  games: readonly TeamCommandGameInput[],
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
        { key: `game-${game.gameId}`, kind: 'game', label: matchup, context: game.commandContext ?? 'NBA game', path, searchTerms: teamTerms },
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

/** NHL game/team search targets all open the loaded game's page. */
export function nhlSlateCommandRows(games: readonly TeamCommandGameInput[]): SlateCommandRow[] {
  const aliases = (name: string) => [name, name.normalize('NFD'), name.normalize('NFD').replace(/\p{M}/gu, '')]
  return games.flatMap(game => {
    if (!validId(game.gameId) || !Number.isSafeInteger(game.gameId)) return []
    const path = `/nhl/game/${game.gameId}`
    const matchup = `${game.awayTeam} @ ${game.homeTeam}`
    const terms = [game.awayTeam, game.homeTeam, ...aliases(game.awayTeamName), ...aliases(game.homeTeamName)]
    return [slateCommandRow({
      key: `nhl-${game.gameId}`, path, searchTerms: terms,
      targets: [
        { key: `game-${game.gameId}`, kind: 'game', label: matchup, context: game.commandContext ?? 'NHL game', path, searchTerms: terms },
        { key: `away-${game.awayTeam}`, kind: 'team', label: game.awayTeam, context: game.awayTeamName, path, searchTerms: aliases(game.awayTeamName) },
        { key: `home-${game.homeTeam}`, kind: 'team', label: game.homeTeam, context: game.homeTeamName, path, searchTerms: aliases(game.homeTeamName) },
      ],
    })]
  })
}
