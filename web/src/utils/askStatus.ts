import type { AskSport } from '~/types/ask'

const SPORT_LABELS: Record<AskSport, string> = { nba: 'NBA', nfl: 'NFL', tennis: 'tennis' }

/** What the drawer shows while a tool runs, e.g. "Checking the NBA slate". */
export function toolLabel(name: string, sport: AskSport | null): string {
  const label = sport ? `${SPORT_LABELS[sport]} ` : ''
  switch (name) {
    case 'get_slate':
      return `Checking the ${label}slate`
    case 'get_top_props':
      return `Reading the ${label}prop board`
    case 'get_game_detail':
      return sport === 'tennis' ? 'Opening the tennis match' : `Opening the ${label}game`
    case 'get_player':
      return `Looking up the ${label}player`
    case 'get_model_track_record':
      return `Reading the ${label}model's track record`
    case 'find':
      return 'Searching Lineform'
    default:
      return 'Checking Lineform data'
  }
}
