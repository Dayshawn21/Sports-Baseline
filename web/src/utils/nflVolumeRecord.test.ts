import { describe, expect, it } from 'vitest'
import type { NflLogLossResult, NflModelRanking } from '~/types/nfl'
import type { PropRankingSlice } from '~/types/propRanking'
import {
  NFL_V4_RANKING_MODEL, NFL_VOLUME_RANKING_MODEL, rankingParams, rankingQueryKey, summaryCounts,
} from '~/utils/nflTrackRecord'
import { logLossRows, notFrozenNote, sliceLogLossText, volumeSlices } from '~/utils/nflVolumeRecord'

function slice(oddsType: PropRankingSlice['oddsType'], side: PropRankingSlice['side'], overrides: Partial<PropRankingSlice> = {}): PropRankingSlice {
  return {
    oddsType, side, verdict: 'insufficient', n: 0, weeks: 0, hits: 0, hitRate: null, standardError: null,
    breakEven: 0.577, signal: 'neutral', ...overrides,
  }
}

const RESULT: NflLogLossResult = {
  n: 412, weeks: 4, weeksWon: 3, weeksRequired: 3, blend: 0.6834, raw: 0.6973, half: 0.6931,
  rawDifference: -0.0139, rawStandardError: 0.0061, halfDifference: -0.0097, halfStandardError: 0.0052, passed: false,
}

function record(overrides: Partial<NflModelRanking> = {}): NflModelRanking {
  return {
    gradedAt: '2026-11-20T12:00:00Z', season: 2026, modelVersion: 'nfl-volume-v1', overProbabilityVersion: 'nfl-volume-anchor-v1',
    rule: { minPicks: 200, minWeeks: 4, minPickMargin: 0.03 }, finishedWeeks: [9, 10], lastSettledWeek: 10,
    frozenRows: 230, excluded: {}, coverage: [{ week: 9, lines: 115, frozen: 110 }],
    funnel: { calls: 220, withPOver: 220, picks: 14, bets: 14 },
    slices: [
      slice('standard', 'over', { n: 9, weeks: 2, hits: 6, hitRate: 0.667, standardError: 0.157 }),
      slice('standard', 'under'), slice('goblin', 'over'), slice('demon', 'over'),
    ],
    logLoss: {
      progress: RESULT,
      slices: [
        { oddsType: 'standard', side: 'over', state: 'evaluated', logLoss: null },
        { oddsType: 'standard', side: 'under', state: 'evaluated', logLoss: null },
        { oddsType: 'goblin', side: 'over', state: 'not_frozen', logLoss: null },
        { oddsType: 'demon', side: 'over', state: 'not_frozen', logLoss: null },
      ],
    },
    ...overrides,
  }
}

describe('volumeSlices', () => {
  it('keeps the four canonical slices, with goblin and demon reading Not frozen', () => {
    const views = volumeSlices(record())

    expect(views.map((view) => [view.label, view.status, view.frozen])).toEqual([
      ['Standard over', 'No verdict yet', true], ['Standard under', 'No verdict yet', true],
      ['Goblin over', 'Not frozen', false], ['Demon over', 'Not frozen', false],
    ])
    expect(views.every((view) => view.tone === 'neutral')).toBe(true)
  })

  it('shows the verdict once the API reports one, and never a color', () => {
    const adopted = record({ slices: [slice('standard', 'over', { verdict: 'adopt', signal: 'positive', n: 210, weeks: 5 }), ...record().slices.slice(1)] })
    const view = volumeSlices(adopted)[0]

    expect(view.status).toBe('Adopt')
    expect(view.tone).toBe('neutral')
  })

  it('treats a record without the log-loss block as standard-only evaluated', () => {
    const views = volumeSlices(record({ logLoss: undefined }))
    expect(views.map((view) => view.frozen)).toEqual([true, true, false, false])
  })

  it('keeps zero picks as zero, not as a failure', () => {
    const view = volumeSlices(record())[1]
    expect(view.slice.n).toBe(0)
    expect(view.status).toBe('No verdict yet')
  })

  it('names only the payouts that have no frozen row yet', () => {
    expect(notFrozenNote(volumeSlices(record()))).toBe('Not frozen yet: Goblin over, Demon over (no frozen row for that payout).')
  })

  it('has nothing to say once every payout has a frozen row', () => {
    const everyPayout = record({
      logLoss: {
        progress: RESULT,
        slices: record().logLoss!.slices.map((item) => ({ ...item, state: 'evaluated' as const })),
      },
    })
    const views = volumeSlices(everyPayout)

    expect(views.every((view) => view.frozen)).toBe(true)
    expect(notFrozenNote(views)).toBeNull()
  })

  it('names every payout before the first freeze', () => {
    const none = record({
      logLoss: { progress: RESULT, slices: record().logLoss!.slices.map((item) => ({ ...item, state: 'not_frozen' as const })) },
    })
    expect(notFrozenNote(volumeSlices(none))).toBe(
      'Not frozen yet: Standard over, Standard under, Goblin over, Demon over (no frozen row for that payout).',
    )
  })

  it('shows a rung slice as evaluated and its log-loss result once the API reports one', () => {
    const demon = record({
      logLoss: {
        progress: RESULT,
        slices: record().logLoss!.slices.map((item) => (item.oddsType === 'demon'
          ? { ...item, state: 'evaluated' as const, logLoss: RESULT } : item)),
      },
    })
    const view = volumeSlices(demon).find((item) => item.label === 'Demon over')!

    expect(view.frozen).toBe(true)
    expect(view.status).toBe('No verdict yet')
    expect(sliceLogLossText(view)).toBe('3 of 4 weeks (need 3) · not passed')
  })

  it('shows no per-slice log-loss text before the sample is fixed or with no lines', () => {
    const views = volumeSlices(record())
    expect(views.every((view) => sliceLogLossText(view) === null)).toBe(true)
    expect(sliceLogLossText({ ...views[0], logLoss: { ...RESULT, n: 0 } })).toBeNull()
  })
})

describe('logLossRows', () => {
  it('lists the blend, both references, the differences and the weeks won', () => {
    expect(logLossRows(RESULT)).toEqual([
      { label: 'Settled lines', value: '412' },
      { label: 'Blend', value: '0.683' },
      { label: 'Raw volume', value: '0.697' },
      { label: 'Coin flip', value: '0.693' },
      { label: 'Blend minus raw', value: '-0.014 ± 0.006' },
      { label: 'Blend minus coin flip', value: '-0.010 ± 0.005' },
      { label: 'Weeks won', value: '3 of 4 (need 3)' },
    ])
  })

  it('reads an empty or missing sample as not started', () => {
    expect(logLossRows({ ...RESULT, n: 0 })).toEqual([{ label: 'Settled lines', value: '0' }])
    expect(logLossRows(null)).toEqual([{ label: 'Settled lines', value: '0' }])
    expect(logLossRows(undefined)).toEqual([{ label: 'Settled lines', value: '0' }])
  })

  it('omits a missing standard error and signs a positive difference', () => {
    const rows = logLossRows({ ...RESULT, rawDifference: 0.02, rawStandardError: null })
    expect(rows.find((row) => row.label === 'Blend minus raw')?.value).toBe('+0.020')
  })
})

describe('volume query and summary scope', () => {
  it('adds the selector only for the volume model and keys it apart from v4 and the season', () => {
    expect(rankingParams(2026, NFL_VOLUME_RANKING_MODEL)).toEqual({ season: 2026, model_version: 'nfl-volume-v1' })
    expect(rankingParams(2026)).toEqual({ season: 2026 })
    expect(rankingQueryKey(2026, NFL_VOLUME_RANKING_MODEL)).not.toEqual(rankingQueryKey(2026, NFL_V4_RANKING_MODEL))
    expect(rankingQueryKey(2026, NFL_VOLUME_RANKING_MODEL)).not.toEqual(rankingQueryKey(2027, NFL_VOLUME_RANKING_MODEL))
  })

  it('keeps a volume record out of the v4 summary', () => {
    const pending = summaryCounts(undefined, undefined)
    const counts = summaryCounts(record(), undefined)
    expect(counts.slicesAdopted).toBe(pending.slicesAdopted)
    expect(counts.lastSettledWeek).toBe(pending.lastSettledWeek)
  })
})
