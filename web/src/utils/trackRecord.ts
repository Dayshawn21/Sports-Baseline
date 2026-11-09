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

export interface CalibrationDatum {
  /** Mean predicted p1 win chance in the bin, in percent. */
  predicted: number
  /** Actual p1 win rate in the bin, in percent. */
  actual: number
  n: number
  range: string
}

/** Calibration bins in percent for the chart; the dot's area follows `n`. */
export function calibrationChartData(bins: TrackCalibrationBin[]): CalibrationDatum[] {
  return bins.map((bin) => ({
    predicted: bin.meanPredicted * 100,
    actual: bin.actualRate * 100,
    n: bin.n,
    range: `${Math.round(bin.low * 100)}-${Math.round(bin.high * 100)}%`,
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
