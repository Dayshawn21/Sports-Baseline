import type { NflPlayerUsage, NflSlateGame, NflSlateLine } from '~/types/nfl'
import { nflGameProps } from '~/utils/nflGameProps'
import { edgeShare, type NflBoardLine } from '~/utils/nflPropBoard'
import { groupNflPropRows } from '~/utils/nflPropRows'

export function isNflSpecialist(position: string | null): boolean {
  return position === 'K' || position === 'P'
}

export function nflPlayerMarketLink(playerId: number, market: string): string {
  return `/nfl/player/${playerId}?market=${encodeURIComponent(market)}#game-log`
}

export const SPECIALIST_COLUMNS = {
  K: [
    { field: 'fgMade', label: 'FG', market: 'field_goals_made' },
    { field: 'patMade', label: 'PAT', market: null },
    { field: 'kickingPoints', label: 'Kicking pts', market: 'kicking_points' },
  ],
  P: [{ field: 'punts', label: 'Punts', market: 'punts' }],
} as const

export interface NflPlayerWeekLine {
  row: NflBoardLine
  /** The line's rank on the week-wide board; null for lines the board does not rate. */
  rank: number | null
  /** Null for anytime TD, which carries no edge until 25c. */
  edgeShare: number | null
  alternates: NflSlateLine[]
}

export interface NflPlayerWeek {
  game: NflSlateGame
  lines: NflPlayerWeekLine[]
}

/**
 * The player's full-game lines this week, ranked and scored against the week-wide board as the
 * game page reads it, so a row never disagrees with `/nfl/board`. Null when the player has no line.
 */
export function playerWeekLines(games: NflSlateGame[], playerId: number, now = new Date()): NflPlayerWeek | null {
  const game = games.find(item => item.lines.some(line => line.playerId === playerId))
  if (!game) return null
  const alternates = new Map(groupNflPropRows(game.lines).map(item => [item.primary.lineId, item.alternates]))
  const lines = nflGameProps(games, game.gameId, 'all', 'full_game', now).flatMap(({ category, rateable, other }) => [
    ...rateable.filter(item => item.row.playerId === playerId).map(item => ({ row: item.row, rank: item.rank as number | null })),
    ...other.filter(row => row.playerId === playerId).map(row => ({ row, rank: null })),
  ].map(({ row, rank }) => ({
    row,
    rank,
    edgeShare: row.market === 'anytime_touchdown' ? null : edgeShare(row, category.referenceLine),
    alternates: alternates.get(row.lineId) ?? [],
  })))
  return lines.length ? { game, lines } : null
}

/** API usage names (snake case) to the usage fields they read. */
export const USAGE_FIELDS: Record<string, keyof Pick<NflPlayerUsage, 'passingAttempts' | 'rushingAttempts' | 'targets' | 'receptions' | 'snapPct'>> = {
  passing_attempts: 'passingAttempts',
  rushing_attempts: 'rushingAttempts',
  targets: 'targets',
  receptions: 'receptions',
  snap_pct: 'snapPct',
}

export const USAGE_LABELS: Record<string, string> = {
  passing_attempts: 'Pass attempts',
  rushing_attempts: 'Carries',
  targets: 'Targets',
  receptions: 'Receptions',
  snap_pct: 'Snap share',
}

export interface NflUsageBar {
  week: number
  value: number | null
  heightPct: number
  previousSeason: boolean
}

export interface NflUsageRow {
  stat: string
  label: string
  /** "16.7 / g", or "64%" for snap share; "--" with no values. */
  average: string
  bars: NflUsageBar[]
}

/** One usage row. Snap share scales to 100%; counts scale to the row's largest game. */
export function usageBars(usage: NflPlayerUsage[], stat: string): NflUsageRow {
  const field = USAGE_FIELDS[stat]
  const values = usage.map(game => (field ? game[field] : null))
  const present = values.filter((value): value is number => value !== null)
  const isShare = stat === 'snap_pct'
  const scale = isShare ? 1 : Math.max(0, ...present)
  const mean = present.length ? present.reduce((sum, value) => sum + value, 0) / present.length : null
  return {
    stat,
    label: USAGE_LABELS[stat] ?? stat,
    average: mean === null ? '--' : isShare ? `${Math.round(mean * 100)}%` : `${mean.toFixed(1)} / g`,
    bars: usage.map((game, index) => {
      const value = values[index]
      return {
        week: game.week,
        value,
        heightPct: value === null || scale <= 0 ? 0 : Math.min(100, (value / scale) * 100),
        previousSeason: game.previousSeason,
      }
    }),
  }
}

const NAME_SUFFIXES = new Set(['jr', 'sr', 'ii', 'iii', 'iv', 'v'])

/** "JC" for James Cook; a suffix such as "Jr." or "II" is skipped. */
export function playerInitials(name: string): string {
  const words = name.split(/\s+/).filter(word => word && !NAME_SUFFIXES.has(word.replace(/\./g, '').toLowerCase()))
  if (!words.length) return '--'
  const first = words[0][0] ?? ''
  const last = words.length > 1 ? words[words.length - 1][0] ?? '' : ''
  return `${first}${last}`.toUpperCase()
}

/** The chip labels for a focus market: the focus stat, then the volume stat. */
export const FOCUS_LABELS: Record<string, { focus: string, volume: string, line: string }> = {
  passing_yards: { focus: 'Pass yds / g', volume: 'Attempts / g', line: 'Pass yds line' },
  rushing_yards: { focus: 'Rush yds / g', volume: 'Carries / g', line: 'Rush yds line' },
  receiving_yards: { focus: 'Rec yds / g', volume: 'Targets / g', line: 'Rec yds line' },
}
