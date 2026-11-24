import { NFL_SEASON_OPTIONS } from '~/utils/nflLabels'

export const NFL_LAST_WEEK = 18

export interface NflWeek { season: number, week: number }

/** Newest first, as the season options list them. */
const SEASONS = NFL_SEASON_OPTIONS.map(option => option.value)

function isWeek(value: number): boolean {
  return Number.isInteger(value) && value >= 1 && value <= NFL_LAST_WEEK
}

/** The week a `/nfl?season=&week=` link names; a missing or invalid value is null and falls back to the current week. */
export function readNflWeekLink(params: URLSearchParams): { season: number | null, week: number | null } {
  const season = Number(params.get('season'))
  const week = Number(params.get('week'))
  return {
    season: params.has('season') && SEASONS.includes(season) ? season : null,
    week: params.has('week') && isWeek(week) ? week : null,
  }
}

export function nflWeekPath({ season, week }: NflWeek): string {
  return `/nfl?season=${season}&week=${week}`
}

/** One week back and forward; week 1 steps to the previous listed season's week 18, and the listed ends have no neighbor. */
export function nflWeekNeighbors({ season, week }: NflWeek, seasons: readonly number[] = SEASONS): { previous: NflWeek | null, next: NflWeek | null } {
  const ordered = [...seasons].sort((left, right) => left - right)
  const index = ordered.indexOf(season)
  const older = index > 0 ? ordered[index - 1] : undefined
  const newer = index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : undefined
  return {
    previous: week > 1 ? { season, week: week - 1 } : older === undefined ? null : { season: older, week: NFL_LAST_WEEK },
    next: week < NFL_LAST_WEEK ? { season, week: week + 1 } : newer === undefined ? null : { season: newer, week: 1 },
  }
}

/** The week picker's options, grouped by season. Values are `season-week` strings, since Ant options need one flat key. */
export function nflWeekPickerOptions() {
  return NFL_SEASON_OPTIONS.map(season => ({
    label: season.label,
    title: season.label,
    options: Array.from({ length: NFL_LAST_WEEK }, (_, index) => ({
      value: nflWeekKey({ season: season.value, week: index + 1 }),
      label: `Week ${index + 1}`,
    })),
  }))
}

export function nflWeekKey({ season, week }: NflWeek): string {
  return `${season}-${week}`
}

export function parseNflWeekKey(key: string): NflWeek | null {
  const [season, week] = key.split('-').map(Number)
  return SEASONS.includes(season) && isWeek(week) ? { season, week } : null
}
