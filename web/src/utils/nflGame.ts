import type { NflGameOdds, NflTeamContext, NflWeather } from '~/types/nfl'
import { spreadLabel } from '~/utils/nflGameModel'
import { devigP1, fmtAmerican } from '~/utils/odds'
import { parseMatchId } from '~/utils/tennisMatch'

export const parseGameId = parseMatchId

const MISSING = '--'

const KICKOFF_FORMAT = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Chicago', weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
})

/** `Sun, Sep 27, 12:00 PM CT`; the owner reads kickoffs in Central time. */
export function kickoffLabel(startUtc: string | null): string {
  if (startUtc === null) return 'Kickoff time not set'
  const time = Date.parse(startUtc)
  return Number.isNaN(time) ? 'Kickoff time not set' : `${KICKOFF_FORMAT.format(time)} CT`
}

export function hasKickedOff(startUtc: string | null, now: Date): boolean {
  if (startUtc === null) return false
  const time = Date.parse(startUtc)
  return !Number.isNaN(time) && time <= now.getTime()
}

export function conditionsLabel(weather: NflWeather): string {
  if (weather.venueType === 'dome') return 'Indoor'
  if (!weather.forecastFor) return 'Forecast unavailable'
  const temperature = weather.temperatureF === null ? MISSING : weather.temperatureF.toFixed(0)
  const wind = weather.windMph === null ? MISSING : weather.windMph.toFixed(0)
  return `${temperature}°F · wind ${wind} mph`
}

export function recordLabel(context: NflTeamContext | null): string {
  return context === null || context.games === 0 ? 'No games yet' : `${context.wins}-${context.losses}`
}

export interface NflMarketCell {
  value: string
  detail: string
}

export function marketImpliedPoints(odds: NflGameOdds | null): { home: number, away: number } | null {
  if (!odds || odds.homeSpread === null || odds.total === null) return null
  const { homeSpread, total } = odds
  if (!Number.isFinite(homeSpread) || !Number.isFinite(total) || total < Math.abs(homeSpread)) return null
  return { home: (total - homeSpread) / 2, away: (total + homeSpread) / 2 }
}

export interface NflGameMarket {
  spread: NflMarketCell
  winProbability: NflMarketCell
  total: NflMarketCell
}

/** The market row of the game page: the displayed book's spread, de-vigged moneyline and total. */
export function gameMarket(odds: NflGameOdds | null, homeTeam: string, awayTeam: string): NflGameMarket | null {
  if (odds === null) return null
  const home = devigP1(odds.homeMoneyline, odds.awayMoneyline)
  return {
    spread: {
      value: odds.homeSpread === null ? MISSING : spreadLabel(odds.homeSpread, homeTeam, awayTeam),
      detail: odds.book,
    },
    winProbability: {
      value: home === null ? MISSING : `${homeTeam} ${(home * 100).toFixed(1)}%`,
      detail: home === null ? 'No moneyline' : `${fmtAmerican(odds.homeMoneyline)} / ${fmtAmerican(odds.awayMoneyline)} de-vigged`,
    },
    total: { value: odds.total === null ? MISSING : odds.total.toFixed(1), detail: odds.book },
  }
}
