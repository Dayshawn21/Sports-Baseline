import type { NflLogLossResult, NflModelRanking, NflVolumeSliceState } from '~/types/nfl'
import type { PropRankingSlice } from '~/types/propRanking'
import { sliceLabel, verdictLabel } from '~/utils/nflTrackRecord'

export const VOLUME_NOTE = 'Volume model reference (receptions only). A slice needs 200 picks over 4+ weeks and a log-loss win before it can adopt; until then it only shows progress.'
export const VOLUME_NOT_FROZEN_NOTE = 'Not frozen: only standard full-game lines are frozen for this model, so goblin and demon lines have no sample.'
export const VOLUME_LOG_LOSS_NOTE = 'Log loss is a progress read on every settled standard line of the finished weeks. It is not a verdict.'

export interface VolumeSliceView {
  key: string
  label: string
  slice: PropRankingSlice
  frozen: boolean
  status: string
  tone: 'neutral'
  logLoss: NflLogLossResult | null
}

const num = (value: number | null) => (value === null ? '--' : value.toFixed(3))

function difference(value: number | null, standardError: number | null): string {
  if (value === null) return '--'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(3)}${standardError === null ? '' : ` ± ${standardError.toFixed(3)}`}`
}

/** The four canonical slices with their state; verdicts stay gray until the API reports one. */
export function volumeSlices(data: NflModelRanking): VolumeSliceView[] {
  const states = new Map<string, NflVolumeSliceState>((data.logLoss?.slices ?? []).map((item) => [`${item.oddsType}-${item.side}`, item]))
  return data.slices.map((slice) => {
    const key = `${slice.oddsType}-${slice.side}`
    const state = states.get(key)
    const frozen = state === undefined ? slice.oddsType === 'standard' : state.state === 'evaluated'
    return {
      key, label: sliceLabel(slice.oddsType, slice.side), slice, frozen,
      status: frozen ? (slice.verdict === 'insufficient' ? 'No verdict yet' : verdictLabel(slice.verdict)) : 'Not frozen',
      tone: 'neutral' as const,
      logLoss: state?.logLoss ?? null,
    }
  })
}

export interface LogLossRow {
  label: string
  value: string
}

/** The progress block as label and value rows; an empty sample reads as not started, never as a loss. */
export function logLossRows(result: NflLogLossResult | null | undefined): LogLossRow[] {
  if (!result || result.n === 0) return [{ label: 'Settled lines', value: '0' }]
  return [
    { label: 'Settled lines', value: String(result.n) },
    { label: 'Blend', value: num(result.blend) },
    { label: 'Raw volume', value: num(result.raw) },
    { label: 'Coin flip', value: num(result.half) },
    { label: 'Blend minus raw', value: difference(result.rawDifference, result.rawStandardError) },
    { label: 'Blend minus coin flip', value: difference(result.halfDifference, result.halfStandardError) },
    { label: 'Weeks won', value: `${result.weeksWon} of ${result.weeks} (need ${result.weeksRequired})` },
  ]
}
