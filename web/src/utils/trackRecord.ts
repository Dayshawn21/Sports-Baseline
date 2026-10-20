import type { LossComparison, ModelPredictionsResponse, ModelVersionCount, TrackCalibrationBin, TrackGroupScores, TrackSignal } from '~/types/tennis'

/** Green and red come only from a server-side 2 SE signal, never from a raw number. */
export function signalClass(signal: TrackSignal): string {
  if (signal === 'positive') return 'is-positive'
  if (signal === 'negative') return 'is-negative'
  return ''
}

/** How many standard errors a difference sits from zero, e.g. "0.9 SE". */
export function seMultiple(mean: number, standardError: number | null): string {
  if (standardError == null || standardError <= 0) return '—'
  return `${(Math.abs(mean) / standardError).toFixed(1)} SE`
}

export type EnsembleVerdict = 'Ahead' | 'Not ahead' | 'No data'

export function pairedLossText(comparison: LossComparison): string {
  const mean = `${comparison.mean >= 0 ? '+' : ''}${comparison.mean.toFixed(4)}`
  return comparison.standardError == null
    ? `${mean} (SE unavailable)`
    : `${mean} +/- ${comparison.standardError.toFixed(4)}`
}

export function ensembleVerdictText(group: TrackGroupScores | undefined): EnsembleVerdict {
  const ensemble = group?.components.find((c) => c.name === 'ensemble')
  if (!group || group.n === 0 || !ensemble?.vsMarket) return 'No data'
  return ensemble.vsMarket.signal === 'positive' ? 'Ahead' : 'Not ahead'
}

/** Switch options in the API's order (served first), each labeled with its settled count. */
export function versionOptions(versions: ModelVersionCount[]): { value: string, label: string }[] {
  return versions.map((v) => ({
    value: v.modelVersion,
    label: `${v.modelVersion}${v.served ? ' (served)' : ''} · ${v.settled.toLocaleString('en-US')} settled`,
  }))
}

/** Why the prediction sections are empty when the version being served has nothing settled yet. */
export function unsettledVersionNote(data: ModelPredictionsResponse): string | null {
  const selected = data.versions.find((v) => v.modelVersion === data.modelVersion)
  if (!selected?.served || data.counts.graded > 0) return null
  const older = data.versions.length > 1 ? ' Earlier versions keep their own record in the switch.' : ''
  return `No ${data.modelVersion} prediction has settled yet; it is the version being served, so its record starts as matches finish.${older}`
}

export interface ChartBox {
  left: number
  right: number
  top: number
  bottom: number
}

export interface CalibrationPoint {
  x: number
  y: number
  r: number
  bin: TrackCalibrationBin
}

const MIN_RADIUS = 3
const RADIUS_RANGE = 4

/** Predicted on x, actual on y; the dot's area grows with the bin's match count. */
export function calibrationPoints(bins: TrackCalibrationBin[], box: ChartBox): CalibrationPoint[] {
  const maxN = Math.max(0, ...bins.map((b) => b.n))
  return bins.map((bin) => ({
    x: box.left + bin.meanPredicted * (box.right - box.left),
    y: box.bottom - bin.actualRate * (box.bottom - box.top),
    r: MIN_RADIUS + (maxN > 0 ? RADIUS_RANGE * Math.sqrt(bin.n / maxN) : 0),
    bin,
  }))
}

/** A rate's plus-or-minus-one-SE range, clamped to 0..1, for the range bars. */
export function rateRange(rate: number, standardError: number | null): { low: number, high: number } | null {
  if (standardError == null) return null
  return { low: Math.max(0, rate - standardError), high: Math.min(1, rate + standardError) }
}

/** Share of the verdict sample filled, 0..1. */
export function sampleProgress(sampleSize: number, target: number): number {
  if (target <= 0) return 0
  return Math.min(1, sampleSize / target)
}
