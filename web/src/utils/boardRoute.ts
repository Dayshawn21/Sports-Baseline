import { parseSlateDate } from '~/utils/slateDates'

export interface BoardPrefetchTarget {
  sport: 'nba' | 'nhl'
  /** As the board page reads it: null (the API's default date) when absent or invalid. */
  date: string | null
}

/** The NBA or NHL props board a hash opens, or null for any other route. */
export function boardPrefetchTarget(hash: string): BoardPrefetchTarget | null {
  const match = /^#?\/(nba|nhl)\/props\/?(?:\?(.*))?$/.exec(hash)
  if (match === null) return null
  const sport = match[1] === 'nba' ? 'nba' : 'nhl'
  return { sport, date: parseSlateDate(new URLSearchParams(match[2] ?? '').get('date')) }
}
