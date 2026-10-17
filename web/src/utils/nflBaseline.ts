import type { NflSlateLine } from '~/types/nfl'

export interface SeasonShare {
  season: number
  lines: number
}

export interface BaselineMix {
  totalLines: number
  staleLines: number
  noBaselineLines: number
  /** Newest season first. */
  seasons: SeasonShare[]
}

export const STALE_FLAG = 'stale_baseline_season'

/** Mirrors `MIN_BASELINE_GAMES` in `api/app/core/nfl_baseline.py`; the API enforces it. */
export const MIN_BASELINE_GAMES = 4

export interface PricedEdges {
  total: number
  currentSeason: number
  stale: number
}

/** Split priced lines by baseline freshness, so the banner never reads as one pool. */
export function summarizePricedEdges(
  lines: Pick<NflSlateLine, 'edge' | 'qualityFlags'>[],
): PricedEdges {
  const priced = lines.filter(line => line.edge !== null)
  const stale = priced.filter(line => line.qualityFlags.includes(STALE_FLAG)).length
  return { total: priced.length, currentSeason: priced.length - stale, stale }
}

/** Count which season each line's baseline came from, for the page banner. */
export function summarizeBaselineMix(lines: Pick<NflSlateLine, 'baselineSeason' | 'qualityFlags'>[]): BaselineMix {
  const counts = new Map<number, number>()
  let staleLines = 0
  let noBaselineLines = 0
  for (const line of lines) {
    // The backend flag is the source of truth, so the banner can never disagree with a row.
    if (line.qualityFlags.includes(STALE_FLAG)) staleLines += 1
    if (line.baselineSeason === null) {
      noBaselineLines += 1
      continue
    }
    counts.set(line.baselineSeason, (counts.get(line.baselineSeason) ?? 0) + 1)
  }
  const seasons = Array.from(counts, ([season, count]) => ({ season, lines: count }))
    .sort((a, b) => b.season - a.season)
  return { totalLines: lines.length, staleLines, noBaselineLines, seasons }
}

/** "252 from 2025, 20 from 2026, 1 with no baseline", largest share first. */
export function describeBaselineMix(mix: BaselineMix): string {
  const parts = [...mix.seasons]
    .sort((a, b) => b.lines - a.lines || b.season - a.season)
    .map(share => `${share.lines} from ${share.season}`)
  if (mix.noBaselineLines) parts.push(`${mix.noBaselineLines} with no baseline`)
  return parts.join(', ')
}
