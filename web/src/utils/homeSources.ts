import type { MatchPrediction } from '~/types/tennis'
import type { NbaSlateGame } from '~/types/nba'
import type { NflSlateGame, NflSlateResponse } from '~/types/nfl'
import type { NhlSlateGame } from '~/types/nhl'
import { centralDay, startLabel, weekdayLabel } from '~/utils/home'
import { nbaPlayerPath } from '~/utils/nbaPlayer'
import { nflPlayerMarketLink } from '~/utils/nflPlayer'
import { nbaSlateSummary, type NbaSlateDigestItem } from '~/utils/nbaSlate'
import { nflSlateSummary, type NflSlateDigestItem } from '~/utils/nflSlate'
import { nhlSlateSummary } from '~/utils/nhlSlate'

/** A gray reference line; the digests' own display strings, never re-ranked across sports. */
export interface HomeGap {
  key: string
  sport: 'nfl' | 'nba'
  playerName: string
  market: string
  matchup: string
  line: string
  model: string
  gap: string
  /** The player page this row opens, with the market tab it came from. */
  path: string
}

export interface HomeNextGame {
  key: string
  title: string
  when: string
}

/** One Central day of the NFL week: how many games are still to come and, for the first, who plays. */
export interface HomeDay {
  key: string
  label: string
  count: number
  title: string
}

/** What one sport contributes to the home, before the lead is chosen. */
export interface HomeSource {
  gameCount: number
  /** Start times in epoch ms of games not yet final; the caller's `now` decides which are still to come. */
  startsMs: number[]
  /** Null where the sport's own slate does not count them (tennis). */
  propLines: number | null
  gaps: HomeGap[]
  nextGames: HomeNextGame[]
  /** Period under the sport name, such as `Week 9`; null for day-based sports. */
  period: string | null
  /** Games still to come by Central day, in order; filled for the NFL only, whose week spans days. */
  days: HomeDay[]
}

export const GAPS_PER_SPORT = 3
export const HERO_NEXT_LIMIT = 3

interface Schedulable {
  key: string
  title: string
  startUtc: string | null
  done: boolean
}

function parsedStart(startUtc: string | null): number | null {
  const time = startUtc === null ? NaN : Date.parse(startUtc)
  return Number.isNaN(time) ? null : time
}

function upcoming(games: Schedulable[]) {
  return games.flatMap(game => {
    const start = parsedStart(game.startUtc)
    return game.done || start === null ? [] : [{ key: game.key, title: game.title, start }]
  })
}

function sourceOf(
  games: Schedulable[],
  now: number,
  rest: Omit<HomeSource, 'startsMs' | 'nextGames' | 'days'>,
): HomeSource {
  const left = upcoming(games)
  const next = left.filter(game => game.start > now).sort((a, b) => a.start - b.start).slice(0, HERO_NEXT_LIMIT)
  return {
    ...rest,
    days: [],
    startsMs: left.map(game => game.start),
    nextGames: next.map(game => ({ key: game.key, title: game.title, when: startLabel(game.start, now) })),
  }
}

function dayGroups(games: Schedulable[], now: number): HomeDay[] {
  const days: HomeDay[] = []
  for (const game of upcoming(games).filter(entry => entry.start > now).sort((a, b) => a.start - b.start)) {
    const key = centralDay(game.start)
    const day = days.find(entry => entry.key === key)
    if (day) day.count += 1
    else days.push({ key, label: weekdayLabel(game.start), count: 1, title: game.title })
  }
  return days
}

function teamGames(games: (NflSlateGame | NbaSlateGame | NhlSlateGame)[]): Schedulable[] {
  return games.map(game => ({
    key: String(game.gameId),
    title: `${game.awayTeam} @ ${game.homeTeam}`,
    startUtc: game.startUtc,
    done: game.status === 'completed',
  }))
}

function gapOf(
  sport: HomeGap['sport'],
  item: { playerName: string, market: string, matchup: string, line: string, model: string, gap: string },
  key: string,
  path: string,
): HomeGap {
  return { key, sport, playerName: item.playerName, market: item.market, matchup: item.matchup, line: item.line, model: item.model, gap: item.gap, path }
}

/** Each sport's own top rows, NFL then NBA. Sorting across sports would compare a share of a reference line with points. */
export function crossSportGaps(nfl: HomeSource, nba: HomeSource): HomeGap[] {
  return [...nfl.gaps.slice(0, GAPS_PER_SPORT), ...nba.gaps.slice(0, GAPS_PER_SPORT)]
}

export function nflSource(slate: NflSlateResponse, digest: NflSlateDigestItem[], now: number): HomeSource {
  const games = teamGames(slate.games)
  return { ...sourceOf(games, now, {
    gameCount: slate.games.length,
    propLines: nflSlateSummary(slate.games, undefined).propLines,
    gaps: digest.slice(0, GAPS_PER_SPORT).map(item => gapOf(
      'nfl', item, String(item.lineId), nflPlayerMarketLink(item.playerId, item.marketKey, { season: slate.season, week: slate.week }),
    )),
    period: `Week ${slate.week}`,
  }), days: dayGroups(games, now) }
}

export function nbaSource(games: NbaSlateGame[], digest: NbaSlateDigestItem[], date: string, now: number): HomeSource {
  return sourceOf(teamGames(games), now, {
    gameCount: games.length,
    propLines: nbaSlateSummary(games).propLines,
    gaps: digest.slice(0, GAPS_PER_SPORT).map(item => gapOf(
      'nba', item, item.key, nbaPlayerPath(item.playerId, { date, market: item.marketKey }),
    )),
    period: null,
  })
}

/** NHL props are line-only with no projection, so it has no gaps to show. */
export function nhlSource(games: NhlSlateGame[], now: number): HomeSource {
  return sourceOf(teamGames(games), now, {
    gameCount: games.length,
    propLines: nhlSlateSummary(games).propLines,
    gaps: [],
    period: null,
  })
}

/** A tennis match counts only with a price on both players, the slate's own bar for a priced match. */
export function isPricedMatch(match: MatchPrediction): boolean {
  return match.p1OddsAmerican != null && match.p2OddsAmerican != null
}

export function tennisSource(matches: MatchPrediction[], now: number): HomeSource {
  // The feed spans two UTC dates, so a late match can arrive in both responses.
  const priced = [...new Map(matches.filter(isPricedMatch).map(match => [match.matchId, match])).values()]
  const games = priced.map(match => ({
    key: String(match.matchId),
    title: `${match.p1Name} vs ${match.p2Name}`,
    startUtc: match.startUtc,
    done: false,
  }))
  return sourceOf(games, now, { gameCount: priced.length, propLines: null, gaps: [], period: null })
}
