import { describe, expect, it } from 'vitest'
import type { NflHistoryResult } from '~/types/nfl'
import type { NflBoardLine } from '~/utils/nflPropBoard'
import { formBars, nflPropCard, pickLabel, recentBars } from '~/utils/nflPropCards'

const EMPTY_SAMPLE = { average: null, values: [] }
const NOW = Date.parse('2026-09-30T12:00:00Z')

function row(overrides: Partial<NflBoardLine> = {}): NflBoardLine {
  return {
    lineId: 7,
    playerId: 7,
    playerName: 'Ladd McConkey',
    position: 'WR',
    opponentTeam: 'MIA',
    opponentPositionAverage: null,
    recentForm: EMPTY_SAMPLE,
    opponentHistory: EMPTY_SAMPLE,
    opponentAllowedHistory: EMPTY_SAMPLE,
    market: 'receiving_yards',
    segment: 'full_game',
    oddsType: 'standard',
    projection: 66.4,
    line: 58.5,
    edge: 7.9,
    gamesInSample: 10,
    baselineSeason: 2026,
    baselineReason: 'current_season',
    opponentAdjustmentPct: null,
    opponentSampleGames: null,
    usageAdjustmentPct: null,
    usageSampleGames: null,
    provider: 'prizepicks',
    fetchedAt: '2026-09-29T12:00:00Z',
    projectionModelVersion: 'opponent-dvp-tg-blend-usage-snap-v4',
    qualityFlags: [],
    bookProbability: null,
    bookProbabilityDevigged: null,
    bookCount: null,
    bookIncludesMargin: null,
    bookFetchedAt: null,
    injuryStatus: null,
    practiceStatus: null,
    injury: null,
    depthPosition: null,
    depthRank: null,
    previousDepthPosition: null,
    previousDepthRank: null,
    snapShare: null,
    snapShareGames: null,
    pOver: null,
    pUnder: null,
    overProbabilityVersion: null,
    gameId: 1,
    awayTeam: 'MIA',
    homeTeam: 'LAC',
    startUtc: null,
    ...overrides,
  }
}

function games(...values: number[]): { average: number, values: NflHistoryResult[] } {
  return { average: 0, values: values.map((value, index) => ({ value, opponentTeam: `T${index}` })) }
}

describe('pickLabel', () => {
  it('reads the side from the edge sign', () => {
    expect(pickLabel(2)).toBe('OVER')
    expect(pickLabel(-2)).toBe('UNDER')
    expect(pickLabel(null)).toBe('--')
  })
})

describe('nflPropCard', () => {
  it('maps an OVER stat line to the strings the table showed', () => {
    const card = nflPropCard(row(), 26.5, NOW)
    expect(card).toMatchObject({
      kind: 'stat', badge: 'LAC', meta: 'WR · MIA @ LAC', unit: 'receiving yards',
      lineText: '58.5', modelText: '66.4', pickLabel: 'OVER', isUnder: false,
      edgeShareText: '+29.8%', edgeText: '+7.9', trust: 'Ready', sampleText: '10g', thin: false,
      bookText: null, snapText: null,
    })
  })

  it('marks an UNDER line', () => {
    const card = nflPropCard(row({ edge: -3.2 }), 32, NOW)
    expect(card).toMatchObject({ pickLabel: 'UNDER', isUnder: true, edgeShareText: '-10.0%', edgeText: '-3.2' })
  })

  it('shows dashes with no edge or no reference line', () => {
    expect(nflPropCard(row({ edge: null, line: null }), 26.5, NOW)).toMatchObject({ pickLabel: '--', isUnder: false, edgeShareText: '--', edgeText: '--', lineText: '--' })
    expect(nflPropCard(row(), null, NOW).edgeShareText).toBe('--')
  })

  it('takes the team from the other side of the game, else the position', () => {
    expect(nflPropCard(row({ opponentTeam: 'LAC' }), 26.5, NOW).badge).toBe('MIA')
    expect(nflPropCard(row({ opponentTeam: null }), 26.5, NOW).badge).toBe('WR')
    expect(nflPropCard(row({ opponentTeam: null, position: null }), 26.5, NOW).badge).toBe('--')
  })

  it('adds kickoff and a partial segment to the meta', () => {
    const card = nflPropCard(row({ segment: 'first_half', startUtc: '2026-10-04T17:00:00Z' }), 26.5, NOW)
    expect(card.meta).toBe('WR · MIA @ LAC · 12:00 PM CT · 1st half')
  })

  it('keeps only the position and a partial segment in the game-page meta', () => {
    expect(nflPropCard(row({ startUtc: '2026-10-04T17:00:00Z' }), 26.5, NOW).gameMeta).toBe('WR')
    expect(nflPropCard(row({ segment: 'first_half' }), 26.5, NOW).gameMeta).toBe('WR · 1st half')
    expect(nflPropCard(row({ position: null }), 26.5, NOW).gameMeta).toBe('--')
  })

  it('flags a thin sample and passes flags through, minus the historical baseline', () => {
    const card = nflPropCard(row({ gamesInSample: 5, qualityFlags: ['historical_baseline', 'stale_baseline_season'] }), 26.5, NOW)
    expect(card).toMatchObject({ sampleText: '5g thin', thin: true, trust: 'Review', flags: ['stale_baseline_season'] })
  })

  it('shows depth only when a depth move is flagged, and the injury tag', () => {
    const depth = { depthPosition: 'WR', depthRank: 1, previousDepthPosition: 'WR', previousDepthRank: 2 }
    expect(nflPropCard(row(depth), 26.5, NOW).depthText).toBeNull()
    expect(nflPropCard(row({ ...depth, qualityFlags: ['depth_promoted'] }), 26.5, NOW).depthText).toBe('WR1 (was WR2)')
    expect(nflPropCard(row({ injuryStatus: 'Questionable' }), 26.5, NOW).injury).toEqual({ label: 'Q', color: 'gold' })
  })

  it('builds an anytime-TD card from the model, books and snap share', () => {
    const td = row({ market: 'anytime_touchdown', projection: 0.52, line: 0.5, edge: null, snapShare: 0.64, snapShareGames: 12 })
    expect(nflPropCard(td, null, NOW)).toMatchObject({ kind: 'td', modelText: '52.0%', bookText: 'No book price', snapText: '64% · 12 g, season-weighted', pickLabel: '--' })
    const priced = nflPropCard({ ...td, bookProbability: 0.58, bookProbabilityDevigged: 0.55, bookCount: 4, bookIncludesMargin: true, bookFetchedAt: '2026-09-30T10:00:00Z' }, null, NOW)
    expect(priced.bookText).toBe('55.0% de-vigged · 4 books · 2h ago')
  })

  it('falls back to the raw market name for an unknown market', () => {
    expect(nflPropCard(row({ market: 'longest_reception' }), 26.5, NOW).unit).toBe('longest_reception')
  })
})

describe('recentBars', () => {
  it('reads oldest to newest and compares each game to the line', () => {
    const { bars } = recentBars(row({ line: 50, recentForm: games(60, 50, 20) }))
    expect(bars.map(bar => [bar.value, bar.vsLine])).toEqual([[20, 'below'], [50, 'push'], [60, 'above']])
    expect(bars.map(bar => bar.opponentTeam)).toEqual(['T2', 'T1', 'T0'])
  })

  it('scales heights and the line mark to the largest of the values and the line', () => {
    expect(recentBars(row({ line: 80, recentForm: games(40, 20) }))).toEqual(expect.objectContaining({ linePct: 100 }))
    expect(recentBars(row({ line: 80, recentForm: games(40, 20) })).bars.map(bar => bar.heightPct)).toEqual([25, 50])
    const low = recentBars(row({ line: 10, recentForm: games(40, 20) }))
    expect([low.bars.map(bar => bar.heightPct), low.linePct]).toEqual([[50, 100], 25])
    expect(recentBars(row({ line: 0.5, recentForm: games(0, 0) })).bars.map(bar => bar.heightPct)).toEqual([0, 0])
  })

  it('returns no bars without history or for anytime TD, and no comparison without a line', () => {
    expect(recentBars(row())).toEqual({ bars: [], linePct: null })
    expect(recentBars(row({ market: 'anytime_touchdown', recentForm: games(1, 0) }))).toEqual({ bars: [], linePct: null })
    const noLine = recentBars(row({ line: null, recentForm: games(30) }))
    expect([noLine.bars[0], noLine.linePct]).toEqual([expect.objectContaining({ heightPct: 100, vsLine: null }), null])
  })

  it('does not draw whole-game history against a partial-segment line', () => {
    const half = recentBars(row({ segment: 'first_half', line: 0.5, recentForm: games(30, 15) }))
    expect([half.bars.map(bar => [bar.heightPct, bar.vsLine]), half.linePct]).toEqual([[[50, null], [100, null]], null])
  })
})

describe('formBars', () => {
  it('draws any sample the way recentBars draws the five-game form', () => {
    const sample = games(60, 50, 20)
    expect(formBars(sample, row({ line: 50 }))).toEqual(recentBars(row({ line: 50, recentForm: sample })))
    expect(formBars(games(1, 0), row({ market: 'anytime_touchdown' }))).toEqual({ bars: [], linePct: null })
  })
})

describe('formBars below zero', () => {
  const heights = (sample: ReturnType<typeof games>, line: number | null) => {
    const drawn = formBars(sample, row({ line }))
    return { bars: drawn.bars.map(bar => [bar.heightPct, bar.bottomPct]), linePct: drawn.linePct }
  }

  it('adds no bottom offset when nothing is below zero, so NFL bars are unchanged', () => {
    const drawn = formBars(games(60, 50, 20), row({ line: 50 }))
    expect(drawn.bars.every(bar => !('bottomPct' in bar))).toBe(true)
    expect(drawn.bars.map(bar => bar.heightPct)).toEqual([(20 / 60) * 100, (50 / 60) * 100, 100])
    expect(drawn.linePct).toBe((50 / 60) * 100)
    expect(formBars(games(0, 0), row({ line: 0.5 })).bars.every(bar => !('bottomPct' in bar))).toBe(true)
  })

  it('places a mixed sample on one signed range with the zero line inside the plot', () => {
    expect(heights(games(3, 0, -2), 1)).toEqual({ bars: [[40, 0], [0, 40], [60, 40]], linePct: 60 })
  })

  it('draws an all-negative sample down from the zero line at the top', () => {
    expect(heights(games(-1, -4), null)).toEqual({ bars: [[100, 0], [25, 75]], linePct: null })
  })

  it('puts a line below zero on the same scale', () => {
    expect(heights(games(2, -2), -1)).toEqual({ bars: [[50, 0], [50, 50]], linePct: 25 })
  })

  it('draws a single negative value to the full height', () => {
    expect(heights(games(-3), null)).toEqual({ bars: [[100, 0]], linePct: null })
  })

  it('still marks above, below and push against a negative line', () => {
    const drawn = formBars(games(1, -1, -3), row({ line: -1 }))
    expect(drawn.bars.map(bar => bar.vsLine)).toEqual(['below', 'push', 'above'])
  })
})
