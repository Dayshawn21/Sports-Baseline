import { describe, expect, it } from 'vitest'
import type { NflVolumeReference } from '~/types/nfl'
import type { NflBoardLine } from '~/utils/nflPropBoard'
import { nflPropCard } from '~/utils/nflPropCards'
import { nflPropDetail } from '~/utils/nflPropDetail'
import { signalSummary } from '~/utils/nflSignal'
import { VOLUME_NOTE, volumeReferenceModel, volumeTableText } from '~/utils/nflVolume'

const NOW = new Date('2026-11-12T12:00:00Z').getTime()
const EMPTY = { average: null, values: [] }

const VOLUME: NflVolumeReference = {
  projection: 5.43, median: 5, line: 5.5, gap: -0.07, gamesInSample: 7, qVol: 0.47, pOver: 0.458, pUnder: 0.452,
  pPush: 0.09, modelVersion: 'nfl-volume-v1', overProbabilityVersion: 'nfl-volume-anchor-v1',
  qualityFlags: ['volume_reference', 'anchor_unvalidated'],
}

function row(overrides: Partial<NflBoardLine> = {}): NflBoardLine {
  return {
    lineId: 70, playerId: 7, playerName: 'Receiver', position: 'WR', opponentTeam: 'BUF',
    gameId: 50, awayTeam: 'BUF', homeTeam: 'MIA', startUtc: '2026-11-13T01:15:00Z',
    market: 'receptions', segment: 'full_game', oddsType: 'standard', projection: 5.1, line: 5.5, edge: -0.4,
    gamesInSample: 7, baselineSeason: 2026, baselineReason: 'current_season',
    projectionModelVersion: 'opponent-dvp-tg-blend-usage-snap-v4',
    recentForm: EMPTY, opponentHistory: EMPTY, opponentAllowedHistory: EMPTY, opponentPositionAverage: null,
    opponentAdjustmentPct: 1.5, opponentSampleGames: 17, usageAdjustmentPct: 0.5, usageSampleGames: 7,
    provider: 'prizepicks', fetchedAt: '2026-11-12T11:00:00Z', qualityFlags: ['historical_baseline'],
    bookProbability: null, bookCount: null, bookIncludesMargin: null, bookFetchedAt: null, bookProbabilityDevigged: null,
    injuryStatus: null, practiceStatus: null, injury: null, depthPosition: null, depthRank: null,
    previousDepthPosition: null, previousDepthRank: null, snapShare: null, snapShareGames: null,
    pOver: 0.45, pUnder: 0.55, overProbabilityVersion: 'nfl-pover-v1',
    ...overrides,
  }
}

describe('volumeReferenceModel', () => {
  it('lists the reference with neutral wording and the not-validated note', () => {
    const model = volumeReferenceModel(row({ volume: VOLUME }))

    expect(model?.title).toBe('Volume model')
    expect(model?.rows).toEqual([
      { label: 'Projection (mean)', value: '5.4' },
      { label: 'Median', value: '5.0' },
      { label: 'Reference gap', value: '-0.1 vs 5.5 line' },
      { label: 'Chance over', value: '46% over · 45% under · 9% push' },
      { label: 'Games behind it', value: '7' },
    ])
    expect(model?.note).toBe(VOLUME_NOTE)
    expect(model?.note).toContain('no betting recommendation')
  })

  it('shows nothing when the field is absent, null, or the market is not receptions', () => {
    expect(volumeReferenceModel(row())).toBeNull()
    expect(volumeReferenceModel(row({ volume: null }))).toBeNull()
    expect(volumeReferenceModel(row({ market: 'receiving_yards', volume: VOLUME }))).toBeNull()
    expect(volumeTableText(row())).toBeNull()
    expect(volumeTableText(row({ volume: null }))).toBeNull()
    expect(volumeTableText(row({ market: 'receiving_yards', volume: VOLUME }))).toBeNull()
  })

  it('keeps a zero projection and a zero gap rather than hiding them', () => {
    const model = volumeReferenceModel(row({ volume: { ...VOLUME, projection: 0, median: 0, gap: 0 } }))
    expect(model?.rows[0].value).toBe('0.0')
    expect(model?.rows[2].value).toBe('0.0 vs 5.5 line')
  })

  it('never uses pick, rank, best or badge wording', () => {
    const text = JSON.stringify(volumeReferenceModel(row({ volume: VOLUME }))) + (volumeTableText(row({ volume: VOLUME })) ?? '')
    expect(text).not.toMatch(/\b(pick|rank|best|lock|bet on)\b/i)
    expect(text).not.toMatch(/\b(OVER|UNDER)\b/)
  })
})

describe('goblin and demon rungs', () => {
  it.each(['goblin', 'demon'])('show nothing for a %s rung even when it carries a companion', (oddsType) => {
    const rung = row({ oddsType, volume: VOLUME })

    expect(volumeReferenceModel(rung)).toBeNull()
    expect(volumeTableText(rung)).toBeNull()
  })

  it('still shows the standard line and ignores a missing payout', () => {
    expect(volumeReferenceModel(row({ oddsType: 'standard', volume: VOLUME }))).not.toBeNull()
    expect(volumeTableText(row({ oddsType: 'standard', volume: VOLUME }))).toBe('Volume 5.4 · 46% over')
    expect(volumeTableText(row({ oddsType: null, volume: VOLUME }))).toBeNull()
  })
})

describe('volumeTableText', () => {
  it('is one short line under the model value', () => {
    expect(volumeTableText(row({ volume: VOLUME }))).toBe('Volume 5.4 · 46% over')
  })
})

describe('v4 presentation is unchanged by the companion', () => {
  it('leaves the card, detail and summary identical', () => {
    const plain = row()
    const mixed = row({ volume: VOLUME })

    expect(nflPropCard(mixed, 5.5, NOW)).toEqual(nflPropCard(plain, 5.5, NOW))
    expect(nflPropDetail(mixed, null, [], NOW)).toEqual(nflPropDetail(plain, null, [], NOW))
    expect(signalSummary(mixed)).toBe(signalSummary(plain))
  })
})
