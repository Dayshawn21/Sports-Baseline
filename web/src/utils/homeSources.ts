import type { MatchPrediction, PropLine } from '~/types/tennis'
import type { NbaSlateGame } from '~/types/nba'
import type { NflSlateGame, NflSlateResponse } from '~/types/nfl'
import type { NhlSlateGame } from '~/types/nhl'
import { centralDay, startLabel, weekdayLabel } from '~/utils/home'
import { nbaPlayerPath } from '~/utils/nbaPlayer'
import { nflPlayerMarketLink } from '~/utils/nflPlayer'
import { nbaSlateSummary, type NbaSlateDigestItem } from '~/utils/nbaSlate'
import { nflSlateSummary, type NflSlateDigestItem } from '~/utils/nflSlate'
import { nhlSlateSummary } from '~/utils/nhlSlate'
import { enrichTennisPropLines, isTennisRateable, marketTitle, marketWinProbabilities, payoutTier } from '~/utils/tennisPropBoard'
import { propPlayerPath } from '~/utils/tennisPlayerProps'

/** A gray reference line; the digests' own display strings, never re-ranked across sports. */
export interface HomeGap {
  key: string
  sport: 'nfl' | 'nba' | 'tennis'
  playerName: string
  market: string
  matchup: string
  line: string
  model: string
  gap: string
  /** The digest's own Central start text, such as `Thu 7:15 PM CT`. */
  when: string
  /** The player page this row opens, with the market tab it came from. */
  path: string
}

/** A gray win-probability row: the side the model rates above the market, in the sport's own order. */
export interface HomeMoneyline {
  key: string
  sport: 'nfl' | 'tennis'
  side: string
  matchup: string
  when: string
  market: string
  model: string
  /** The model's probability minus the market's, in percentage points. */
  gap: string
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
  moneyline: HomeMoneyline[]
  nextGames: HomeNextGame[]
  /** Upcoming games soonest first, longer than `nextGames`; the gaps tabs list it for sports with no gap rows. */
  schedule: HomeNextGame[]
  /** Period under the sport name, such as `Week 9`; null for day-based sports. */
  period: string | null
  /** True when the sport's gap query failed; the games still count. */
  gapsFailed?: boolean
  /** Games still to come by Central day, in order; filled for the NFL only, whose week spans days. */
  days: HomeDay[]
}

export const GAPS_PER_SPORT = 10
export const HERO_NEXT_LIMIT = 3
export const SCHEDULE_LIMIT = 10

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
  rest: Omit<HomeSource, 'startsMs' | 'nextGames' | 'schedule' | 'days' | 'moneyline'> & { moneyline?: HomeMoneyline[] },
): HomeSource {
  const left = upcoming(games)
  const soonest = left.filter(game => game.start > now).sort((a, b) => a.start - b.start)
  const listed = (limit: number) => soonest.slice(0, limit).map(game => ({ key: game.key, title: game.title, when: startLabel(game.start, now) }))
  return {
    ...rest,
    moneyline: rest.moneyline ?? [],
    days: [],
    startsMs: left.map(game => game.start),
    nextGames: listed(HERO_NEXT_LIMIT),
    schedule: listed(SCHEDULE_LIMIT),
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
  item: { playerName: string, market: string, matchup: string, when: string, line: string, model: string, gap: string },
  key: string,
  path: string,
): HomeGap {
  return { key, sport, playerName: item.playerName, market: item.market, matchup: item.matchup, when: item.when, line: item.line, model: item.model, gap: item.gap, path }
}

const pct = (probability: number) => `${(probability * 100).toFixed(1)}%`

interface WinSides {
  key: string
  sport: HomeMoneyline['sport']
  matchup: string
  startMs: number
  path: string
  sides: [{ name: string, model: number, market: number }, { name: string, model: number, market: number }]
}

/** Both sides' gaps mirror each other once the market is de-vigged, so the row names the side the model rates higher. */
function moneylineRows(games: WinSides[], now: number): HomeMoneyline[] {
  return games
    .filter(game => game.startMs > now)
    .map(game => {
      const [first, second] = game.sides
      const side = first.model - first.market >= second.model - second.market ? first : second
      return { game, side, diff: side.model - side.market }
    })
    .sort((a, b) => b.diff - a.diff || a.game.key.localeCompare(b.game.key))
    .slice(0, GAPS_PER_SPORT)
    .map(({ game, side, diff }) => ({
      key: game.key, sport: game.sport, side: side.name, matchup: game.matchup, when: `${startLabel(game.startMs, now)} CT`,
      market: pct(side.market), model: pct(side.model), gap: `+${(diff * 100).toFixed(1)} pp`, path: game.path,
    }))
}

function nflWinSides(games: NflSlateGame[]): WinSides[] {
  return games.flatMap(game => {
    const start = parsedStart(game.startUtc)
    const home = game.model?.homeWinProbability
    const market = game.model?.marketHomeWinProbability
    if (game.status === 'completed' || start === null || home == null || market == null) return []
    return [{
      key: String(game.gameId), sport: 'nfl' as const, matchup: `${game.awayTeam} @ ${game.homeTeam}`, startMs: start,
      path: `/nfl/game/${game.gameId}`,
      sides: [{ name: game.homeTeam, model: home, market }, { name: game.awayTeam, model: 1 - home, market: 1 - market }],
    }]
  })
}

function tennisWinSides(matches: MatchPrediction[]): WinSides[] {
  return matches.flatMap(match => {
    const start = parsedStart(match.startUtc)
    if (start === null || match.p1WinProb == null || match.p2WinProb == null || match.p1OddsAmerican == null || match.p2OddsAmerican == null) return []
    const [p1Market, p2Market] = marketWinProbabilities(match.p1OddsAmerican, match.p2OddsAmerican)
    return [{
      key: String(match.matchId), sport: 'tennis' as const, matchup: `${match.p1Name} vs ${match.p2Name}`, startMs: start,
      path: `/tennis/match/${match.matchId}`,
      sides: [{ name: match.p1Name, model: match.p1WinProb, market: p1Market }, { name: match.p2Name, model: match.p2WinProb, market: p2Market }],
    }]
  })
}

export function nflSource(slate: NflSlateResponse, digest: NflSlateDigestItem[], now: number): HomeSource {
  const games = teamGames(slate.games)
  return { ...sourceOf(games, now, {
    gameCount: slate.games.length,
    propLines: nflSlateSummary(slate.games, undefined).propLines,
    gaps: digest.slice(0, GAPS_PER_SPORT).map(item => gapOf(
      'nfl', item, String(item.lineId), nflPlayerMarketLink(item.playerId, item.marketKey, { season: slate.season, week: slate.week }),
    )),
    moneyline: moneylineRows(nflWinSides(slate.games), now),
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

function signedShare(value: number): string {
  return `${value < 0 ? '-' : '+'}${Math.abs(value).toFixed(1)}%`
}

/**
 * The tennis board's standard PrizePicks lines as gray gap rows: the projection against the line as a share of
 * the line, the NFL rows' unit. Lines whose projection ran on the model total are left out (48a: it ran low).
 */
export function tennisGapRows(props: PropLine[], matches: MatchPrediction[], now: number): HomeGap[] {
  const seen = new Set<string>()
  const ranked = enrichTennisPropLines(props, matches, 'prizepicks')
    .filter(line => payoutTier(line) === 'standard' && isTennisRateable(line) && !(line.dataQualityFlags ?? []).includes('no_market_total'))
    .flatMap(line => {
      const start = parsedStart(line.startTime ?? null)
      return start === null || start <= now || line.edgePct == null ? [] : [{ line, start, edge: line.edgePct }]
    })
    .sort((a, b) => Math.abs(b.edge) - Math.abs(a.edge) || (a.line.playerName ?? '').localeCompare(b.line.playerName ?? '') || a.line.id - b.line.id)
  const rows: HomeGap[] = []
  for (const { line, start, edge } of ranked) {
    const path = propPlayerPath(line, matches)
    const player = String(line.playerId ?? line.playerName)
    if (path === null || seen.has(player)) continue
    seen.add(player)
    rows.push({
      key: String(line.id), sport: 'tennis', playerName: line.playerName ?? 'Unknown player', market: marketTitle(line.statType),
      matchup: line.matchup ?? '', when: `${startLabel(start, now)} CT`, line: Number(line.line).toFixed(1),
      model: (line.statAvg as number).toFixed(1), gap: signedShare(edge), path,
    })
    if (rows.length === GAPS_PER_SPORT) break
  }
  return rows
}

export function tennisSource(matches: MatchPrediction[], now: number, props: PropLine[] = []): HomeSource {
  // The feed spans two UTC dates, so a late match can arrive in both responses.
  const priced = [...new Map(matches.filter(isPricedMatch).map(match => [match.matchId, match])).values()]
  const games = priced.map(match => ({
    key: String(match.matchId),
    title: `${match.p1Name} vs ${match.p2Name}`,
    startUtc: match.startUtc,
    done: false,
  }))
  return sourceOf(games, now, {
    gameCount: priced.length, propLines: null, gaps: tennisGapRows(props, matches, now), moneyline: moneylineRows(tennisWinSides(priced), now), period: null,
  })
}
