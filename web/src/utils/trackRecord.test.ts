import { describe, expect, it } from 'vitest'
import type { ModelPredictionsResponse, ModelVersionCount, TrackCalibrationBin, TrackGroupScores } from '~/types/tennis'
import { calibrationPoints, ensembleVerdictText, pairedLossText, rateRange, sampleProgress, seMultiple, signalClass, unsettledVersionNote, versionOptions } from '~/utils/trackRecord'

function group(signal: 'positive' | 'neutral' | null, n = 308): TrackGroupScores {
  return {
    group: 'ATP+WTA',
    n,
    components: [
      { name: 'market', logLoss: 0.5255, brier: 0.1737, vsMarket: null },
      {
        name: 'ensemble', logLoss: 0.5316, brier: 0.1768,
        vsMarket: signal ? { mean: 0.006, standardError: 0.0068, signal } : null,
      },
    ],
  }
}

function bin(meanPredicted: number, actualRate: number, n: number): TrackCalibrationBin {
  return { low: 0, high: 0.1, n, meanPredicted, actualRate }
}

describe('signalClass', () => {
  it('maps only the server signal to a color class', () => {
    expect(signalClass('positive')).toBe('is-positive')
    expect(signalClass('negative')).toBe('is-negative')
    expect(signalClass('neutral')).toBe('')
  })
})

describe('seMultiple', () => {
  it('reports the distance from zero in standard errors, either sign', () => {
    expect(seMultiple(0.006, 0.0068)).toBe('0.9 SE')
    expect(seMultiple(-0.0213, 0.011)).toBe('1.9 SE')
  })

  it('shows a dash when there is no error bar', () => {
    expect(seMultiple(0.01, null)).toBe('—')
    expect(seMultiple(0.01, 0)).toBe('—')
  })
})

describe('ensembleVerdictText', () => {
  it('says ahead only on a positive signal', () => {
    expect(ensembleVerdictText(group('positive'))).toBe('Ahead')
    expect(ensembleVerdictText(group('neutral'))).toBe('Not ahead')
  })

  it('says no data for a missing or empty group', () => {
    expect(ensembleVerdictText(undefined)).toBe('No data')
    expect(ensembleVerdictText(group('neutral', 0))).toBe('No data')
    expect(ensembleVerdictText(group(null))).toBe('No data')
  })
})

describe('pairedLossText', () => {
  it('shows signed loss differences with one standard error', () => {
    expect(pairedLossText({ mean: -0.01234, standardError: 0.00321, signal: 'positive' })).toBe('-0.0123 +/- 0.0032')
    expect(pairedLossText({ mean: 0.01234, standardError: 0.00321, signal: 'neutral' })).toBe('+0.0123 +/- 0.0032')
  })

  it('distinguishes singleton uncertainty from an observed zero error', () => {
    expect(pairedLossText({ mean: 0, standardError: null, signal: 'neutral' })).toBe('+0.0000 (SE unavailable)')
    expect(pairedLossText({ mean: 0, standardError: 0, signal: 'neutral' })).toBe('+0.0000 +/- 0.0000')
  })
})

describe('calibrationPoints', () => {
  const box = { left: 30, right: 310, top: 10, bottom: 250 }

  it('places predicted on x and actual on y, inverted for SVG', () => {
    const [point] = calibrationPoints([bin(0.5, 0.25, 10)], box)
    expect(point.x).toBe(170)
    expect(point.y).toBe(190)
  })

  it('scales the radius by the square root of the bin count', () => {
    const [small, large] = calibrationPoints([bin(0.2, 0.2, 25), bin(0.8, 0.8, 100)], box)
    expect(large.r).toBe(7)
    expect(small.r).toBe(5)
  })

  it('returns nothing for no bins', () => {
    expect(calibrationPoints([], box)).toEqual([])
  })
})

describe('rateRange', () => {
  it('spans one standard error each side, clamped to 0..1', () => {
    expect(rateRange(0.484, 0.016)).toEqual({ low: 0.484 - 0.016, high: 0.484 + 0.016 })
    expect(rateRange(0.95, 0.1)).toEqual({ low: 0.85, high: 1 })
  })

  it('has no range without a standard error', () => {
    expect(rateRange(0.67, null)).toBeNull()
  })
})

describe('sampleProgress', () => {
  it('fills toward the verdict sample and stops at full', () => {
    expect(sampleProgress(50, 200)).toBe(0.25)
    expect(sampleProgress(230, 200)).toBe(1)
    expect(sampleProgress(0, 0)).toBe(0)
  })
})

function predictions(modelVersion: string, graded: number, versions: ModelVersionCount[]): ModelPredictionsResponse {
  return {
    gradedAt: '2026-10-01T12:00:00Z',
    modelVersion,
    counts: { settled: 0, otherVersions: 0, incomplete: 0, graded, withMarket: 0, withClose: 0 },
    groups: [],
    ensembleMarketGroups: [],
    calibration: [],
    clv: [],
    versions,
  }
}

const VERSIONS: ModelVersionCount[] = [
  { modelVersion: 'ensemble-v3+lgbm-v6', settled: 0, served: true },
  { modelVersion: 'ensemble-v1+lgbm-v6', settled: 1155, served: false },
]

describe('versionOptions', () => {
  it('keeps the API order and labels the served version and counts', () => {
    expect(versionOptions(VERSIONS)).toEqual([
      { value: 'ensemble-v3+lgbm-v6', label: 'ensemble-v3+lgbm-v6 (served) · 0 settled' },
      { value: 'ensemble-v1+lgbm-v6', label: 'ensemble-v1+lgbm-v6 · 1,155 settled' },
    ])
  })
})

describe('unsettledVersionNote', () => {
  it('explains an empty served version and points at earlier ones', () => {
    const note = unsettledVersionNote(predictions('ensemble-v3+lgbm-v6', 0, VERSIONS))
    expect(note).toContain('No ensemble-v3+lgbm-v6 prediction has settled yet')
    expect(note).toContain('Earlier versions')
  })

  it('says nothing once the served version has graded matches', () => {
    expect(unsettledVersionNote(predictions('ensemble-v3+lgbm-v6', 4, VERSIONS))).toBeNull()
  })

  it('says nothing for an older version, whose empty state speaks for itself', () => {
    expect(unsettledVersionNote(predictions('ensemble-v1+lgbm-v6', 0, VERSIONS))).toBeNull()
  })

  it('omits the pointer when no earlier version exists', () => {
    expect(unsettledVersionNote(predictions('ensemble-v3+lgbm-v6', 0, VERSIONS.slice(0, 1)))).not.toContain('Earlier')
  })
})
