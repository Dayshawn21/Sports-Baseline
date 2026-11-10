export type LogoSport = 'nba' | 'nhl' | 'nfl'

// ESPN's NHL logo files use shorter codes than our stored team codes.
const ESPN_CODE_OVERRIDES: Record<LogoSport, Record<string, string>> = {
  nba: {},
  nhl: { LAK: 'la', SJS: 'sj', TBL: 'tb' },
  nfl: {},
}

export function isLogoSport(sport: string): sport is LogoSport {
  return sport === 'nba' || sport === 'nhl' || sport === 'nfl'
}

/** ESPN's keyless logo URL for a stored team code, or null when there is no code to look up. */
export function teamLogoUrl(sport: LogoSport, code: string): string | null {
  const trimmed = code.trim()
  if (trimmed === '') return null
  const espnCode = ESPN_CODE_OVERRIDES[sport][trimmed.toUpperCase()] ?? trimmed.toLowerCase()
  return `https://a.espncdn.com/i/teamlogos/${sport}/500/${espnCode}.png`
}
