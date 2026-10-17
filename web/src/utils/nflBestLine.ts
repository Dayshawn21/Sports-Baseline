import type { NflBestLine, NflBestMarket, NflBestSide, NflFairPrice } from '~/types/nfl'
import { fmtAmerican } from '~/utils/odds'

const BOOKS: Record<string, [full: string, short: string]> = {
  bet365: ['Bet365', 'B365'],
  draftkings: ['DraftKings', 'DK'],
  fanduel: ['FanDuel', 'FD'],
  betrivers: ['BetRivers', 'BR'],
  betonlineag: ['BetOnline', 'BOL'],
  betus: ['BetUS', 'BetUS'],
  lowvig: ['LowVig', 'LV'],
  mybookieag: ['MyBookie', 'MB'],
}

const MARKET_LABELS: Record<NflBestMarket['market'], string> = { moneyline: 'Moneyline', spread: 'Spread', total: 'Total' }

export function bookLabel(book: string, short = false): string {
  const known = BOOKS[book]
  if (known) return short ? known[1] : known[0]
  return book.charAt(0).toUpperCase() + book.slice(1)
}

/** "12m ago", "5h ago", "2d ago"; a clock-skewed future time reads as just now. */
export function ageLabel(fetchedAt: string, now: Date): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - Date.parse(fetchedAt)) / 60000))
  if (minutes < 60) return `${minutes}m ago`
  if (minutes < 48 * 60) return `${Math.floor(minutes / 60)}h ago`
  return `${Math.floor(minutes / 1440)}d ago`
}

function signedLine(line: number): string {
  return line > 0 ? `+${line.toFixed(1)}` : line < 0 ? line.toFixed(1) : 'PK'
}

/** The side as a bettor reads it: "TB +9.5", "DAL", "O 47.5". */
export function sideLabel(side: NflBestSide, homeTeam: string, awayTeam: string): string {
  if (side.side === 'over' || side.side === 'under') return `${side.side === 'over' ? 'O' : 'U'} ${side.line?.toFixed(1) ?? ''}`.trim()
  const team = side.side === 'home' ? homeTeam : awayTeam
  if (side.line === null) return team
  return `${team} ${signedLine(side.side === 'home' ? side.line : -side.line)}`
}

/** "+0.1% vs fair" at the fair line, "+1.5 pts vs fair" off it, null without a fair price. */
export function vsFairLabel(side: NflBestSide): string | null {
  if (side.evPct !== null) {
    const pct = (side.evPct * 100).toFixed(1)
    // A price that rounds to fair carries no sign: "-0.0%" reads as a loss.
    if (Number(pct) === 0) return '0.0% vs fair'
    return `${side.evPct > 0 ? '+' : ''}${pct}% vs fair`
  }
  if (side.pointsVsFair !== null) return `${side.pointsVsFair >= 0 ? '+' : ''}${side.pointsVsFair.toFixed(1)} pts vs fair`
  return null
}

/** The fair line ("DAL -8.0", "47.5"), or the home win chance for a moneyline ("DAL 78.7%"). */
export function fairLabel(market: NflBestMarket['market'], fair: NflFairPrice, homeTeam: string, awayTeam: string): string {
  if (market === 'moneyline' || fair.line === null) return `${homeTeam} ${(fair.firstProbability * 100).toFixed(1)}%`
  if (market === 'total') return fair.line.toFixed(1)
  return fair.line <= 0 ? `${homeTeam} ${signedLine(fair.line)}` : `${awayTeam} ${signedLine(-fair.line)}`
}

export interface NflBestLineSideRow {
  label: string
  price: string
  book: string
  age: string
  vsFair: string | null
}

export interface NflBestLineRow {
  market: string
  sides: NflBestLineSideRow[]
  /** Null when there is no fair price for the market. */
  fair: { label: string, source: string, age: string } | null
}

export function nflBestLineRows(bestLine: NflBestLine, homeTeam: string, awayTeam: string, now: Date): NflBestLineRow[] {
  return bestLine.markets.map(market => ({
    market: MARKET_LABELS[market.market],
    sides: market.sides.map(side => ({
      label: sideLabel(side, homeTeam, awayTeam),
      price: fmtAmerican(side.odds),
      book: bookLabel(side.book),
      age: ageLabel(side.fetchedAt, now),
      vsFair: vsFairLabel(side),
    })),
    fair: market.fair === null ? null : {
      label: fairLabel(market.market, market.fair, homeTeam, awayTeam),
      source: market.fair.source === 'pinnacle' ? 'Pinnacle' : 'Consensus',
      age: ageLabel(market.fair.fetchedAt, now),
    },
  }))
}
