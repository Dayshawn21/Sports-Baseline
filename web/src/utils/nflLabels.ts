/** Display labels shared by the NFL slate and the prop-line board. */
import { fmtTimeCT } from '~/utils/format'

export const NFL_SEASON_OPTIONS = [
  { value: 2026, label: '2026' },
  { value: 2025, label: '2025' },
  { value: 2024, label: '2024 historical' },
]

export const NFL_WEEK_OPTIONS = Array.from({ length: 18 }, (_, index) => ({ value: index + 1, label: `Week ${index + 1}` }))

export const MARKET_LABELS: Record<string, string> = {
  passing_yards: 'Passing yards', passing_attempts: 'Pass attempts', passing_completions: 'Pass completions',
  rushing_yards: 'Rushing yards', rushing_attempts: 'Rush attempts', receiving_yards: 'Receiving yards',
  receptions: 'Receptions', anytime_touchdown: 'Anytime TD', fantasy_points: 'Fantasy points',
  receiving_targets: 'Rec targets', passing_touchdowns: 'Pass TDs', interceptions: 'Interceptions',
  rushing_receiving_yards: 'Rush + rec yards', passing_rushing_yards: 'Pass + rush yards',
  passing_rushing_receiving_touchdowns: 'Pass + rush + rec TDs', field_goals_made: 'FG made',
  kicking_points: 'Kicking points', punts: 'Punts',
}

export const SEGMENT_LABELS: Record<string, string> = {
  full_game: 'Full game', first_half: '1st half', second_half: '2nd half',
  q1: '1st quarter', q2: '2nd quarter', q3: '3rd quarter', q4: '4th quarter', season: 'Season total',
}

export const SEGMENT_COLORS: Record<string, string> = {
  full_game: 'green', first_half: 'blue', second_half: 'blue',
  q1: 'geekblue', q2: 'geekblue', q3: 'geekblue', q4: 'geekblue', season: 'orange',
}

// Full game first, then in-game segments, with season totals last: a season line
// is a different animal from a single-game line and should not lead.
const SEGMENT_ORDER = ['full_game', 'first_half', 'second_half', 'q1', 'q2', 'q3', 'q4', 'season']

export const ODDS_TYPE_LABELS: Record<string, string> = {
  standard: 'Standard', goblin: 'Goblin', demon: 'Demon',
}

/** Goblin and demon lines are moved off the market price on purpose. */
export const ODDS_TYPE_COLORS: Record<string, string> = {
  standard: 'default', goblin: 'gold', demon: 'volcano',
}

export const FLAG_LABELS: Record<string, string> = {
  historical_baseline: 'Baseline from past results, not a live model',
  small_sample: 'Fewer than 4 games behind this average',
  stale_baseline_season: 'Baseline is from a different season than this line',
  partial_season_baseline: 'This season is still being played, so the average will move',
  segment_mismatch: 'Whole-game average cannot be compared to this segment',
  non_standard_line: 'Alternate line with an adjusted payout, not the market price',
  team_not_in_game: "Player's current roster team is not in this game, so opponent and home/away are unknown",
  injury_out: 'Ruled out on this week\'s final injury report',
  injury_doubtful: 'Listed doubtful on this week\'s injury report',
  injury_questionable: 'Listed questionable on this week\'s injury report',
  depth_promoted: 'Moved up the depth chart since the previous week (display only, not in the model)',
  depth_demoted: 'Moved down the depth chart since the previous week (display only, not in the model)',
  depth_new: 'New team or position on the depth chart, or first listing',
  snap_share_unavailable: 'No offensive snap history, so the TD model used the position average snap share',
}

export const BASELINE_REASON_LABELS: Record<string, string> = {
  current_season: "This line's own season, with at least 4 games",
  previous_season: "Not enough games yet this season, so the most recent earlier season with at least 4",
  largest_sample: 'No season has 4 games, so the season with the most',
  no_data: 'No completed games in any loaded season',
  blended_seasons: 'Up to three seasons, newest weighted most, pulled toward the position TD rate',
  current_previous_blend: 'This season and last, weighted by games, last season counted at 0.6',
}

export function segmentRank(segment: string): number {
  const index = SEGMENT_ORDER.indexOf(segment)
  return index === -1 ? SEGMENT_ORDER.length : index
}

export function segmentLabel(segment: string): string {
  return SEGMENT_LABELS[segment] ?? segment
}

export function marketLabel(market: string): string {
  return MARKET_LABELS[market] ?? market
}

export function formatTime(value: string | null): string {
  const time = value ? Date.parse(value) : Number.NaN
  if (Number.isNaN(time)) return 'Start time unavailable'
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Chicago',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }).format(time) + ' CT'
}

/** Compact Central kickoff time for dense board rows. */
export function formatKickoffTime(value: string | null): string {
  return fmtTimeCT(value)
}

/** One past game: anytime TD is scored or not, other markets are the stat itself. */
export function formatHistoryValue(market: string, value: number): string {
  if (market === 'anytime_touchdown') return value > 0 ? 'TD' : 'No TD'
  return formatProjection(market, value)
}

/** Anytime TD is a probability; every other market is a raw stat count. */
export function formatProjection(market: string, value: number | null): string {
  if (value === null) return '--'
  return market === 'anytime_touchdown' ? `${(value * 100).toFixed(1)}%` : value.toFixed(1)
}

// Mirrors TEAM_GAME_DVP_MARKETS in api/app/core/nfl_projection.py: these markets'
// opponent average is the whole position's total per game, not one player's.
const TEAM_GAME_DVP_MARKETS = new Set(['passing_completions'])

export function matchupAllowedLabel(market: string, position: string | null, average: number | null, games: number | null): string {
  const allowed = TEAM_GAME_DVP_MARKETS.has(market)
    ? `${formatProjection(market, average)} to ${position ? `${position}s` : 'the position'} per game`
    : `${formatProjection(market, average)} allowed`
  return `${allowed} · ${games ?? 0} games`
}
