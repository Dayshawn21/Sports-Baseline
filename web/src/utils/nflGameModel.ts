import type { NflGameModel, NflGameNotes, NflGameOdds, NflQbChange } from '~/types/nfl'

export interface NflGameModelCell {
  model: string
  market: string
  /** Null when there is no market value to compare against. */
  gap: string | null
}

export interface NflGameModelSummary {
  spread: NflGameModelCell
  winProbability: NflGameModelCell
  total: NflGameModelCell
}

/** The strip's fixed caveat: the model is context beside the market, never a pick. */
export const NFL_GAME_MODEL_CAVEAT = 'Team-strength model, display only. It did not beat closing lines in 2022-2025 testing; not a pick.'

const NO_MARKET = 'No market line'
const MATCHES = 'Matches market'

/** A book-sign home spread named by its favorite: `CHI -2.3`, `PHI -1.5`, or `PK`. */
export function spreadLabel(homeSpread: number, homeTeam: string, awayTeam: string): string {
  if (Math.abs(homeSpread) < 0.05) return 'PK'
  return homeSpread < 0 ? `${homeTeam} ${homeSpread.toFixed(1)}` : `${awayTeam} -${homeSpread.toFixed(1)}`
}

/** Phrase a home-side difference by the team it leans toward, so no sign needs decoding. */
function leanGap(homeLean: number, unit: string, homeTeam: string, awayTeam: string): string {
  const size = Math.abs(homeLean).toFixed(1)
  if (size === '0.0') return MATCHES
  return `${size} ${unit} more on ${homeLean > 0 ? homeTeam : awayTeam}`
}

function spreadCell(model: NflGameModel, odds: NflGameOdds | null, homeTeam: string, awayTeam: string): NflGameModelCell {
  const modelLabel = spreadLabel(model.homeSpread, homeTeam, awayTeam)
  const market = odds?.homeSpread ?? null
  if (market === null) return { model: modelLabel, market: NO_MARKET, gap: null }
  // Book sign: a lower home spread means more points on the home team.
  return {
    model: modelLabel,
    market: spreadLabel(market, homeTeam, awayTeam),
    gap: leanGap(market - model.homeSpread, 'pts', homeTeam, awayTeam),
  }
}

function winProbabilityCell(model: NflGameModel, homeTeam: string, awayTeam: string): NflGameModelCell {
  const modelLabel = `${homeTeam} ${(model.homeWinProbability * 100).toFixed(1)}%`
  const market = model.marketHomeWinProbability
  if (market === null) return { model: modelLabel, market: NO_MARKET, gap: null }
  return {
    model: modelLabel,
    market: `${homeTeam} ${(market * 100).toFixed(1)}%`,
    gap: leanGap((model.homeWinProbability - market) * 100, 'pts', homeTeam, awayTeam),
  }
}

function totalCell(model: NflGameModel, odds: NflGameOdds | null): NflGameModelCell {
  const modelLabel = model.total.toFixed(1)
  const market = odds?.total ?? null
  if (market === null) return { model: modelLabel, market: NO_MARKET, gap: null }
  const difference = model.total - market
  const size = Math.abs(difference).toFixed(1)
  return {
    model: modelLabel,
    market: market.toFixed(1),
    gap: size === '0.0' ? MATCHES : `${size} ${difference > 0 ? 'over' : 'under'} market`,
  }
}

/** Away then home; empty while notes are unavailable or neither QB changed. */
export function qbChanges(notes: NflGameNotes | undefined): NflQbChange[] {
  if (notes === undefined) return []
  return [notes.awayQbChange, notes.homeQbChange].filter(change => change !== null)
}

/** One sentence per reason, each naming its week, then why it matters to the model. */
export function qbChangeText(change: NflQbChange): string {
  const { team, usualStarter, injuryStatus, injuryWeek, lastGameQb, lastGameWeek, previousQb1 } = change
  const sentences = [
    injuryStatus !== null && injuryWeek !== null
      ? `${usualStarter}, the usual starter, was listed ${injuryStatus} in week ${injuryWeek}.`
      : `${usualStarter} is the usual starter.`,
    lastGameQb !== null && lastGameWeek !== null ? `${lastGameQb} led ${team} in passes in week ${lastGameWeek}.` : null,
    previousQb1 !== null ? `${usualStarter} replaced ${previousQb1} as QB1 on the latest depth chart.` : null,
  ]
  return `${team} QB change: ${sentences.filter(Boolean).join(' ')} The model is built from past scores and does not adjust for this.`
}

/** Display strings for the model strip, or null when the game has no model line. */
export function nflGameModelSummary(
  model: NflGameModel | null, odds: NflGameOdds | null, homeTeam: string, awayTeam: string,
): NflGameModelSummary | null {
  if (model === null) return null
  return {
    spread: spreadCell(model, odds, homeTeam, awayTeam),
    winProbability: winProbabilityCell(model, homeTeam, awayTeam),
    total: totalCell(model, odds),
  }
}
