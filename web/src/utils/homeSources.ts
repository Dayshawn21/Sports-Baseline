import type { MatchPrediction } from '~/types/tennis'
import type { NbaSlateGame } from '~/types/nba'
import type { NflSlateGame, NflSlateResponse } from '~/types/nfl'
import type { NhlSlateGame } from '~/types/nhl'
import { startLabel } from '~/utils/home'
import { nbaSlateSummary, type NbaSlateDigestItem } from '~/utils/nbaSlate'
import { nflSlateSummary, type NflSlateDigestItem } from '~/utils/nflSlate'
import { nhlSlateSummary } from '~/utils/nhlSlate'

/** A gray reference line for the hero; the digests' own display strings, never re-ranked here. */
export interface HomeGap {
  key: string
  playerName: string
  market: string
  matchup: string
  line: string
  gap: string
}

export interface HomeNextGame {
  key: string
  title: string
  when: string
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
}

export const HERO_GAP_LIMIT = 3
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
  rest: { gameCount: number, propLines: number | null, gaps: HomeGap[], period: string | null },
): HomeSource {
  const left = upcoming(games)
  const next = left.filter(game => game.start > now).sort((a, b) => a.start - b.start).slice(0, HERO_NEXT_LIMIT)
  return {
    ...rest,
    startsMs: left.map(game => game.start),
    nextGames: next.map(game => ({ key: game.key, title: game.title, when: startLabel(game.start, now) })),
  }
}

function teamGames(games: (NflSlateGame | NbaSlateGame | NhlSlateGame)[]): Schedulable[] {
  return games.map(game => ({
    key: String(game.gameId),
    title: `${game.awayTeam} @ ${game.homeTeam}`,
    startUtc: game.startUtc,
    done: game.status === 'completed',
  }))
}

function gapOf(item: { playerName: string, market: string, matchup: string, line: string, gap: string }, key: string): HomeGap {
  return { key, playerName: item.playerName, market: item.market, matchup: item.matchup, line: item.line, gap: item.gap }
}

export function nflSource(slate: NflSlateResponse, digest: NflSlateDigestItem[], now: number): HomeSource {
  return sourceOf(teamGames(slate.games), now, {
    gameCount: slate.games.length,
    propLines: nflSlateSummary(slate.games, undefined).propLines,
    gaps: digest.slice(0, HERO_GAP_LIMIT).map(item => gapOf(item, String(item.lineId))),
    period: `Week ${slate.week}`,
  })
}

export function nbaSource(games: NbaSlateGame[], digest: NbaSlateDigestItem[], now: number): HomeSource {
  return sourceOf(teamGames(games), now, {
    gameCount: games.length,
    propLines: nbaSlateSummary(games).propLines,
    gaps: digest.slice(0, HERO_GAP_LIMIT).map(item => gapOf(item, item.key)),
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
