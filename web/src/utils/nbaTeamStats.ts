import type { NbaTeamStat, NbaTeamStatRate, NbaTeamStatsContext } from '~/types/nba'

export const NBA_TEAM_STATS: ReadonlyArray<{ key: NbaTeamStat, label: string }> = [
  { key: 'points', label: 'Points' },
  { key: 'rebounds', label: 'Rebounds' },
  { key: 'assists', label: 'Assists' },
  { key: 'threes_made', label: 'Made threes' },
  { key: 'blocks', label: 'Blocks' },
]

export interface NbaTeamRateText {
  value: string
  rank: string
  sample: string
  notes: string[]
}

export function nbaTeamRateText(rate: NbaTeamStatRate, completedGames: number): NbaTeamRateText {
  const available = rate.perGame !== null
  const notes: string[] = []
  if (rate.games < completedGames) notes.push('Partial coverage')
  if (available && rate.games > 0 && rate.games < 3) notes.push('Small sample')
  return {
    value: rate.perGame === null ? '--' : rate.perGame.toFixed(1),
    rank: available && rate.rank !== null ? `Rank ${rate.rank} of ${rate.rankedTeams}` : 'Unranked',
    sample: `${rate.games} of ${completedGames} games`,
    notes,
  }
}

export type NbaOpponentContext = { kind: 'unavailable', message: string } | {
  kind: 'matched'
  opponent: string
  measure: string
  rate: NbaTeamStatRate
  completedGames: number
  season: number
  beforeDate: string
}

export function nbaOpponentContext(
  context: NbaTeamStatsContext | null | undefined, team: string | null, market: string,
): NbaOpponentContext {
  const measure = NBA_TEAM_STATS.find(stat => stat.key === market)
  if (!measure) return { kind: 'unavailable', message: 'Team allowed stats are not available for this market.' }
  if (!context) return { kind: 'unavailable', message: 'Team stats unavailable.' }
  const isAway = team === context.away.team
  const isHome = team === context.home.team
  if (isAway === isHome) return { kind: 'unavailable', message: 'Opponent unavailable: the line team does not identify one game side.' }
  const opponent = isAway ? context.home : context.away
  return {
    kind: 'matched', opponent: opponent.team, measure: measure.label.toLowerCase(),
    rate: opponent.stats[measure.key].allowed, completedGames: opponent.completedGames,
    season: context.season, beforeDate: context.beforeDate,
  }
}
