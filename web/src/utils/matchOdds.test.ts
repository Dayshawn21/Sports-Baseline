import { describe, expect, it } from 'vitest'
import type { MatchOddsRow } from '~/types/tennis'
import { bookLabel, buildMovementSeries, chartScale, latestPerBook, preferredSeries, project, seriesForSide, summarizeMove, type BookSeries } from '~/utils/matchOdds'

function row(book: string, fetchedAt: string, p1Odds: number | null, p2Odds: number | null, line: number | null = null): MatchOddsRow {
  return { book, fetchedAt, p1Odds, p2Odds, line }
}

const T1 = '2026-09-27T19:45:00Z'
const T2 = '2026-09-27T23:00:00Z'
const T3 = '2026-09-28T05:17:00Z'

describe('buildMovementSeries', () => {
  it('de-vigs each moneyline row into a p1 probability, per book', () => {
    const series = buildMovementSeries([
      row('draftkings', T1, 148, -180),
      row('bet365', T1, 150, -190),
      row('draftkings', T2, 122, -148),
    ], 'moneyline')

    expect(series.map((s) => s.book)).toEqual(['draftkings', 'bet365'])
    expect(series[0].points.map((p) => p.at)).toEqual([T1, T2])
    // +148 / -180: raw 0.40323 and 0.64286, normalized to 0.38546
    expect(series[0].points[0].value).toBeCloseTo(0.38546, 4)
    // +122 / -148: raw 0.45045 and 0.59677, normalized to 0.43014
    expect(series[0].points[1].value).toBeCloseTo(0.43014, 4)
  })

  it('skips a one-sided moneyline row rather than charting a raw price', () => {
    const series = buildMovementSeries([row('draftkings', T1, 148, null), row('draftkings', T2, 122, -148)], 'moneyline')

    expect(series[0].points).toHaveLength(1)
  })

  it('charts the line for total games and skips rows without one', () => {
    const series = buildMovementSeries([
      row('bet365', T1, -120, -110, 22.5),
      row('bet365', T2, -125, -105, null),
      row('bet365', T3, -110, -120, 23.5),
    ], 'total_games')

    expect(series[0].points.map((p) => p.value)).toEqual([22.5, 23.5])
  })

  it('sorts each book oldest first even when rows arrive out of order', () => {
    const series = buildMovementSeries([row('draftkings', T3, 120, -150), row('draftkings', T1, 150, -190)], 'moneyline')

    expect(series[0].points.map((p) => p.at)).toEqual([T1, T3])
  })

  it('keeps a book with a single row', () => {
    expect(buildMovementSeries([row('betfair exchange', T1, 115, -140)], 'moneyline')[0].points).toHaveLength(1)
  })

  it('returns no series for no rows', () => {
    expect(buildMovementSeries([], 'moneyline')).toEqual([])
  })
})

function series(book: string, values: number[]): BookSeries {
  return { book, points: values.map((value, i) => ({ at: `2026-09-28T0${i}:00:00Z`, value })) }
}

describe('preferredSeries', () => {
  it('reads DraftKings first, then Bet365, whatever the order', () => {
    expect(preferredSeries([series('Betfair Exchange', [0.4]), series('bet365', [0.4]), series('DraftKings', [0.4])])?.book).toBe('DraftKings')
    expect(preferredSeries([series('betfair exchange', [0.4]), series('betonline.ag', [0.4])])?.book).toBe('betonline.ag')
  })

  it('reads FanDuel after stored Bet365 and before the exchange', () => {
    expect(preferredSeries([series('Betfair Exchange', [0.4]), series('FanDuel', [0.4])])?.book).toBe('FanDuel')
    expect(preferredSeries([series('fanduel', [0.4]), series('bet365', [0.4])])?.book).toBe('bet365')
  })

  it('falls back to any book, and to null for none', () => {
    expect(preferredSeries([series('pinnacle', [0.4])])?.book).toBe('pinnacle')
    expect(preferredSeries([])).toBeNull()
  })
})

describe('summarizeMove', () => {
  it('measures a move toward the model in points', () => {
    const move = summarizeMove(series('draftkings', [0.40, 0.42, 0.43]), 0.524)

    expect(move?.open).toBe(0.40)
    expect(move?.latest).toBe(0.43)
    expect(move?.towardModelPts).toBeCloseTo(3, 6)
    expect(move?.direction).toBe('toward')
  })

  it('reads a move away from the model as negative', () => {
    const move = summarizeMove(series('draftkings', [0.45, 0.41]), 0.524)

    expect(move?.towardModelPts).toBeCloseTo(-4, 6)
    expect(move?.direction).toBe('away')
  })

  it('calls an unchanged price flat', () => {
    expect(summarizeMove(series('draftkings', [0.45, 0.45]), 0.524)?.direction).toBe('flat')
  })

  it('crossing the model counts only the change in distance', () => {
    // 0.50 is 2.4 pts short of 0.524; 0.55 is 2.6 past it, so it moved 0.2 pts away.
    expect(summarizeMove(series('draftkings', [0.50, 0.55]), 0.524)?.towardModelPts).toBeCloseTo(-0.2, 6)
  })

  it('reports open and latest without a model, for totals', () => {
    expect(summarizeMove(series('bet365', [22.5, 23.5]), null)).toEqual({
      open: 22.5, latest: 23.5, towardModelPts: null, direction: null,
    })
  })

  it('is null for a book with no points', () => {
    expect(summarizeMove({ book: 'draftkings', points: [] }, 0.5)).toBeNull()
  })
})

describe('latestPerBook', () => {
  it('keeps each book\'s newest priced row, DraftKings first', () => {
    const rows = [
      row('bet365', T1, 150, -190),
      row('draftkings', T1, 148, -180),
      row('bet365', T2, 140, -175),
      row('draftkings', T3, 122, -148),
    ]

    expect(latestPerBook(rows, 'moneyline').map((r) => [r.book, r.p1Odds])).toEqual([['draftkings', 122], ['bet365', 140]])
  })

  it('skips a newer row that is not usable for the market', () => {
    const rows = [row('bet365', T1, -120, -110, 22.5), row('bet365', T2, null, null, null)]

    expect(latestPerBook(rows, 'total_games')[0].line).toBe(22.5)
    expect(latestPerBook([row('draftkings', T2, 120, null)], 'moneyline')).toEqual([])
  })
})

describe('bookLabel', () => {
  it('names the stored books, including Bet365 under its old key', () => {
    expect(bookLabel('draftkings')).toBe('DraftKings')
    expect(bookLabel('betonline.ag')).toBe('Bet365')
    expect(bookLabel('fanduel')).toBe('FanDuel')
    expect(bookLabel('Betfair Exchange')).toBe('Betfair')
    expect(bookLabel('pinnacle')).toBe('pinnacle')
  })
})

describe('seriesForSide', () => {
  it('leaves p1 alone and flips p2', () => {
    const s = [series('draftkings', [0.4, 0.45])]
    expect(seriesForSide(s, 'p1')).toBe(s)
    expect(seriesForSide(s, 'p2')[0].points.map((p) => p.value)).toEqual([0.6, 0.55])
  })
})

describe('chartScale', () => {
  it('covers every point and the model line, padded', () => {
    const scale = chartScale([series('draftkings', [0.40, 0.44])], [0.52], 0.04)!

    expect(scale.vMin).toBeLessThan(0.40)
    expect(scale.vMax).toBeGreaterThan(0.52)
    expect(scale.tMin).toBe(Date.parse('2026-09-28T00:00:00Z'))
    expect(scale.tMax).toBe(Date.parse('2026-09-28T01:00:00Z'))
  })

  it('widens a flat series to the minimum span, centred', () => {
    const scale = chartScale([series('bet365', [22.5, 22.5])], [], 2)!

    expect(scale.vMax - scale.vMin).toBeCloseTo(2, 10)
    expect((scale.vMax + scale.vMin) / 2).toBeCloseTo(22.5, 10)
  })

  it('is null with nothing to draw', () => {
    expect(chartScale([], [0.5], 0.04)).toBeNull()
  })
})

describe('project', () => {
  const scale = { tMin: Date.parse('2026-09-28T00:00:00Z'), tMax: Date.parse('2026-09-28T10:00:00Z'), vMin: 0.4, vMax: 0.6 }

  it('maps time left to right and value top to bottom', () => {
    expect(project(scale, '2026-09-28T00:00:00Z', 0.6)).toEqual({ x: 0, y: 0 })
    expect(project(scale, '2026-09-28T05:00:00Z', 0.5).x).toBeCloseTo(0.5, 10)
    expect(project(scale, '2026-09-28T10:00:00Z', 0.4).y).toBeCloseTo(1, 10)
  })

  it('centres a single moment', () => {
    expect(project({ ...scale, tMax: scale.tMin }, '2026-09-28T00:00:00Z', 0.5).x).toBe(0.5)
  })
})
