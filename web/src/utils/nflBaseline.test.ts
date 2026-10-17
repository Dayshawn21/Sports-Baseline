import { describe, expect, it } from 'vitest'
import {
  describeBaselineMix, STALE_FLAG, summarizeBaselineMix, summarizePricedEdges,
} from '~/utils/nflBaseline'

const line = (baselineSeason: number | null, stale = false) => ({
  baselineSeason,
  qualityFlags: stale ? ['historical_baseline', STALE_FLAG] : ['historical_baseline'],
})

describe('summarizePricedEdges', () => {
  const priced = (edge: number | null, stale = false) => ({
    edge,
    qualityFlags: stale ? ['historical_baseline', STALE_FLAG] : ['historical_baseline'],
  })

  it('splits priced edges by baseline freshness and ignores unpriced rows', () => {
    const edges = summarizePricedEdges([priced(2.1), priced(24.8, true), priced(null), priced(-3, true)])
    expect(edges).toEqual({ total: 3, currentSeason: 1, stale: 2 })
  })

  it('counts an edge of zero as priced', () => {
    expect(summarizePricedEdges([priced(0)])).toEqual({ total: 1, currentSeason: 1, stale: 0 })
  })
})

describe('summarizeBaselineMix', () => {
  it('counts lines per source season, newest first', () => {
    const mix = summarizeBaselineMix([line(2025, true), line(2026), line(2025, true), line(2024, true)])
    expect(mix.seasons).toEqual([
      { season: 2026, lines: 1 },
      { season: 2025, lines: 2 },
      { season: 2024, lines: 1 },
    ])
    expect(mix.totalLines).toBe(4)
  })

  it('counts stale lines from the backend flag, not by comparing seasons', () => {
    // A 2025 row without the flag is trusted as not stale (e.g. viewing 2025).
    const mix = summarizeBaselineMix([line(2025), line(2024, true)])
    expect(mix.staleLines).toBe(1)
  })

  it('keeps lines with no baseline out of the season counts', () => {
    const mix = summarizeBaselineMix([line(null), line(2026)])
    expect(mix.noBaselineLines).toBe(1)
    expect(mix.seasons).toEqual([{ season: 2026, lines: 1 }])
  })

  it('is empty for an empty slate', () => {
    expect(summarizeBaselineMix([])).toEqual({ totalLines: 0, staleLines: 0, noBaselineLines: 0, seasons: [] })
  })
})

describe('describeBaselineMix', () => {
  it('leads with the largest share and names missing baselines', () => {
    const mix = summarizeBaselineMix([line(2026), line(2025, true), line(2025, true), line(null)])
    expect(describeBaselineMix(mix)).toBe('2 from 2025, 1 from 2026, 1 with no baseline')
  })
})
