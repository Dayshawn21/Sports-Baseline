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

/**
 * ESPN's keyless logo for a stored team code, resized to twice the display size so it stays sharp on 2x
 * screens; null when there is no code. The plain 500px file costs about 31 times the bytes at slate-row
 * size (F-45).
 */
export function teamLogoUrl(sport: LogoSport, code: string, size: number): string | null {
  const trimmed = code.trim()
  if (trimmed === '') return null
  const espnCode = ESPN_CODE_OVERRIDES[sport][trimmed.toUpperCase()] ?? trimmed.toLowerCase()
  const pixels = Math.round(size * 2)
  return `https://a.espncdn.com/combiner/i?img=/i/teamlogos/${sport}/500/${espnCode}.png&w=${pixels}&h=${pixels}`
}
