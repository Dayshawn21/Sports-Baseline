import { describe, expect, it } from 'vitest'
import type { NflSlateGame } from '~/types/nfl'
import { nflGameProps } from '~/utils/nflGameProps'
import { LINE_ONLY_MARKETS } from '~/utils/nflLineOnly'
import { playerWeekLines } from '~/utils/nflPlayer'
import { buildNflPropBoard, isRateable, type NflBoardLine } from '~/utils/nflPropBoard'
import { nflPropCard } from '~/utils/nflPropCards'
import { nflPropDetail } from '~/utils/nflPropDetail'
import { signalSummary } from '~/utils/nflSignal'
import { slateDigest } from '~/utils/nflSlate'
import { TARGETS_PROBABILITY_NOTE, targetsReferenceSummary } from '~/utils/nflTargets'

const NOW = new Date('2026-10-19T12:00:00Z')
const EMPTY = { average: null, values: [] }

function row(overrides: Partial<NflBoardLine> = {}): NflBoardLine {
  return {
    lineId: 70, playerId: 7, playerName: 'Receiver', position: 'WR', opponentTeam: 'BUF',
    gameId: 50, awayTeam: 'BUF', homeTeam: 'MIA', startUtc: '2026-10-20T17:00:00Z',
    market: 'receiving_targets', segment: 'full_game', oddsType: 'standard', projection: 5.25, line: 4.5, edge: 0.75,
    gamesInSample: 8, baselineSeason: 2026, baselineReason: 'current_season', projectionModelVersion: 'nfl-targets-v1',
    recentForm: EMPTY, opponentHistory: EMPTY, opponentAllowedHistory: EMPTY, opponentPositionAverage: null,
    opponentAdjustmentPct: null, opponentSampleGames: null, usageAdjustmentPct: null, usageSampleGames: null,
    provider: 'prizepicks', fetchedAt: '2026-10-19T11:00:00Z', qualityFlags: ['historical_baseline'],
    bookProbability: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null, bookProbabilityDevigged: null,
    injuryStatus: null, practiceStatus: null, injury: null, depthPosition: null, depthRank: null,
    previousDepthPosition: null, previousDepthRank: null, snapShare: null, snapShareGames: null,
    pOver: null, pUnder: null, overProbabilityVersion: null,
    ...overrides,
  }
}

function game(lines: NflBoardLine[]): NflSlateGame {
  return {
    gameId: 50, gameDate: '2026-10-20', startUtc: '2026-10-20T17:00:00Z', status: 'scheduled',
    awayTeam: 'BUF', homeTeam: 'MIA', lines, odds: null, awayContext: null, homeContext: null, model: null,
    weather: { venueType: 'outdoor', forecastFor: null, temperatureF: null, windMph: null,
      windGustMph: null, precipitationProbability: null, fetchedAt: null },
  }
}

describe('Rec Targets reference discovery', () => {
  it('keeps standard full-game references visible by default, sorted by player rather than gap', () => {
    const board = buildNflPropBoard([game([
      row({ playerName: 'Zed', edge: 100 }),
      row({ lineId: 71, playerId: 8, playerName: 'Abe', projection: null, edge: null, gamesInSample: 0 }),
    ])], 'all', NOW)
    expect(board).toHaveLength(1)
    expect(board[0].rateable.map(line => line.playerName)).toEqual(['Abe', 'Zed'])
    expect(board[0].other).toEqual([])
    expect(isRateable(row())).toBe(false)
  })

  it('groups repeated standard snapshots into one reference row', () => {
    const board = buildNflPropBoard([game([row(), row({ lineId: 71, fetchedAt: '2026-10-19T11:30:00Z' })])], 'all', NOW)
    expect(board[0].rateable.map(line => line.lineId)).toEqual([71])
  })

  it('carries no recommendation rank into game or player views', () => {
    const games = [game([row()])]
    expect(nflGameProps(games, 50, 'all', 'full_game', NOW)[0].rateable[0].rank).toBeNull()
    expect(playerWeekLines(games, 7, NOW)?.lines[0].rank).toBeNull()
  })

  it('keeps the eight remaining line-only markets', () => {
    expect(LINE_ONLY_MARKETS).toHaveLength(8)
    expect(LINE_ONLY_MARKETS).not.toContain('receiving_targets')
  })
})

describe('Rec Targets reference wording', () => {
  it.each([0.75, -0.75, 0])('has no pick or rank for a %s gap', edge => {
    const card = nflPropCard(row({ edge }), 1, 4.5, NOW.getTime())
    expect(card).toMatchObject({ kind: 'reference', rank: null, pickLabel: '--', isUnder: false, trust: 'Reference' })
    expect(card.why).toContain('Season-average reference')
    expect(card.why).not.toMatch(/\bOVER\b|\bUNDER\b/)
  })

  it('keeps a real zero distinct from an unavailable projection', () => {
    const zero = row({ projection: 0, edge: -4.5 })
    expect(nflPropCard(zero, 1, 4.5, NOW.getTime()).modelText).toBe('0.0')
    expect(signalSummary(zero)).toContain('reference 0.0')
    expect(nflPropCard(row({ gamesInSample: 4 }), null, 4.5, NOW.getTime())).toMatchObject({ sampleText: '4g', thin: false })
    expect(nflPropCard(row({ projection: null, gamesInSample: 3 }), null, 4.5, NOW.getTime()).sampleText).toBe('3g unavailable')
    expect(targetsReferenceSummary(row({ projection: null, edge: null, gamesInSample: 0 }))).toContain('no valid pre-week targets history')
    expect(targetsReferenceSummary(row({ projection: null, edge: null, gamesInSample: 3 }))).toContain('fewer than 4 valid games')
  })

  it('uses season-average evidence and neutral gap wording in the drawer', () => {
    const detail = nflPropDetail(row(), game([row()]), [], NOW.getTime())
    expect(detail).toMatchObject({ projectionLabel: 'Rec targets reference', projectionText: '5.3',
      deltaText: '+0.8 reference gap vs 4.5 line', hasEdge: false, isUnder: false, referenceNote: TARGETS_PROBABILITY_NOTE })
    expect(detail.breakdown.map(item => [item.label, item.value])).toEqual([
      ['Baseline', '8 games · 2026'], ['Method', 'Season average'], ['Matchup', 'Not used'], ['Usage', 'Not used'], ['Reference', '5.3'],
    ])
    expect(detail.context).toHaveLength(1)
    expect(detail.pOverNote).toBeNull()
    expect(detail.lines[0].pOverText).toBeNull()
    expect(detail.status.find(item => item.label === 'Trust')?.value).toBe('Reference')
  })

  it('does not display a stale probability or v4 adjustment carried by a malformed targets payload', () => {
    const detail = nflPropDetail(row({ pOver: 0.99, pUnder: 0.01, opponentAdjustmentPct: 25 }), null, [], NOW.getTime())
    expect(detail.pOverNote).toBeNull()
    expect(detail.lines[0].pOverText).toBeNull()
    expect(detail.why).not.toContain('Opponent adjustment')
    expect(detail.breakdown.find(item => item.label === 'Matchup')?.value).toBe('Not used')
  })

  it('explains an unavailable baseline in the drawer', () => {
    const detail = nflPropDetail(row({ projection: null, edge: null, gamesInSample: 3, qualityFlags: ['small_sample'] }), null, [], NOW.getTime())
    expect(detail.projectionText).toBe('--')
    expect(detail.why).toContain('fewer than 4 valid games')
  })

  it('labels a slate digest reference without a pick or numbered rank', () => {
    const digest = slateDigest(buildNflPropBoard([game([row()])], 'all', NOW))
    expect(digest[0]).toMatchObject({ market: 'Rec targets reference', modelLabel: 'reference', model: '5.3' })
    expect(digest[0]).not.toHaveProperty('rank')
    expect(digest[0]).not.toHaveProperty('pickLabel')
  })

  it('preserves the existing v4 card and drawer behavior', () => {
    const v4 = row({ market: 'receiving_yards', projectionModelVersion: 'opponent-dvp-tg-blend-usage-snap-v4' })
    expect(nflPropCard(v4, 3, 4.5, NOW.getTime())).toMatchObject({ kind: 'stat', rank: 3, pickLabel: 'OVER', trust: 'Ready' })
    const detail = nflPropDetail(v4, null, [], NOW.getTime())
    expect(detail.hasEdge).toBe(true)
    expect(detail).not.toHaveProperty('referenceNote')
  })
})
