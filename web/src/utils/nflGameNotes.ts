import type { NflLineMove, NflNoteInjury, NflRecentResult, NflTeamForm, NflTeamStat, NflTeamStats } from '~/types/nfl'
import { spreadLabel } from './nflGameModel'

const SINGLE_LINE = 'One line stored, no movement yet'
const UNCHANGED = 'No change'

/** "GB -6.5 → GB -5.5 · 1.0 toward ATL": a rising home line moves toward the away team. */
export function spreadMoveLabel(move: NflLineMove, homeTeam: string, awayTeam: string): string {
  const current = spreadLabel(move.currentLine, homeTeam, awayTeam)
  if (move.move === null) return `${current} · ${SINGLE_LINE}`
  const path = `${spreadLabel(move.openLine, homeTeam, awayTeam)} → ${current}`
  if (move.move === 0) return `${path} · ${UNCHANGED}`
  return `${path} · ${Math.abs(move.move).toFixed(1)} toward ${move.move > 0 ? awayTeam : homeTeam}`
}

/** "46.5 → 42.5 · down 4.0". */
export function totalMoveLabel(move: NflLineMove): string {
  const current = move.currentLine.toFixed(1)
  if (move.move === null) return `${current} · ${SINGLE_LINE}`
  const path = `${move.openLine.toFixed(1)} → ${current}`
  if (move.move === 0) return `${path} · ${UNCHANGED}`
  return `${path} · ${move.move > 0 ? 'up' : 'down'} ${Math.abs(move.move).toFixed(1)}`
}

/** "L 3-34 vs CAR" at home, "W 20-17 @ NYJ" away; the team's own score first. */
export function formLabel(game: NflRecentResult): string {
  return `${game.result} ${game.pointsFor}-${game.pointsAgainst} ${game.isHome ? 'vs' : '@'} ${game.opponent}`
}

/** "Short week · 4 days rest" or "10 days rest"; null when rest is not published. */
export function restLabel(form: Pick<NflTeamForm, 'restDays' | 'shortWeek'>): string | null {
  if (form.restDays === null) return null
  const days = `${form.restDays} day${form.restDays === 1 ? '' : 's'} rest`
  return form.shortWeek ? `Short week · ${days}` : days
}

/** The two teams' injuries in away-then-home order, keeping the API's severity order within each. */
export function injuriesByTeam(injuries: NflNoteInjury[], awayTeam: string, homeTeam: string): [string, NflNoteInjury[]][] {
  return [awayTeam, homeTeam].map(team => [team, injuries.filter(injury => injury.team === team)])
}

type StatKey = Exclude<keyof NflTeamStats, 'team' | 'games' | 'efficiencyGames'>
export type StatKind = 'perGame' | 'epa' | 'rate'

export interface TeamStatRow {
  label: string
  offense: StatKey
  defense: StatKey
  kind: StatKind
}

export const TEAM_STAT_ROWS: TeamStatRow[] = [
  { label: 'Points', offense: 'points', defense: 'pointsAllowed', kind: 'perGame' },
  { label: 'Pass yds', offense: 'passYards', defense: 'passYardsAllowed', kind: 'perGame' },
  { label: 'Rush yds', offense: 'rushYards', defense: 'rushYardsAllowed', kind: 'perGame' },
  { label: 'Plays', offense: 'plays', defense: 'playsAllowed', kind: 'perGame' },
  { label: 'EPA/play', offense: 'epaPerPlay', defense: 'epaPerPlayAllowed', kind: 'epa' },
  { label: 'Success', offense: 'successRate', defense: 'successRateAllowed', kind: 'rate' },
]

/** Under this many games, ranks swing on a single result. */
export const SMALL_SAMPLE_GAMES = 3

/** "24.5", "+0.12", "43%"; "-" when the stat is not loaded. */
export function statValue(stat: NflTeamStat, kind: StatKind): string {
  if (stat.value === null) return '-'
  if (kind === 'epa') return `${stat.value > 0 ? '+' : ''}${stat.value.toFixed(2)}`
  if (kind === 'rate') return `${Math.round(stat.value * 100)}%`
  return stat.value.toFixed(1)
}

/** "1st", "22nd", "11th"; empty when unranked. */
export function rankLabel(rank: number | null): string {
  if (rank === null) return ''
  const teen = rank % 100 >= 11 && rank % 100 <= 13
  const suffix = teen ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[rank % 10] ?? 'th'
  return `${rank}${suffix}`
}

/** "2 games", or "1 game"; null before a team has played. */
export function gamesLabel(stats: Pick<NflTeamStats, 'games'>): string | null {
  if (stats.games === 0) return null
  return `${stats.games} game${stats.games === 1 ? '' : 's'}`
}
