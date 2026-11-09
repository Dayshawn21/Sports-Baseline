export interface MatchupSide { code: string, score: number | null }

/** One form for every game: "JAX @ BAL" before it starts, "JAX 33 @ BAL 10" once both scores are in. */
export function slateMatchup(away: MatchupSide, home: MatchupSide): string {
  if (away.score === null || home.score === null) return `${away.code} @ ${home.code}`
  return `${away.code} ${away.score} @ ${home.code} ${home.score}`
}
