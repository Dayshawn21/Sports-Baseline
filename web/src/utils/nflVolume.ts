import type { NflSlateLine } from '~/types/nfl'
import { formatProjection } from '~/utils/nflLabels'
import { edgeLabel } from '~/utils/nflSignal'

export const VOLUME_NOTE = 'Gray reference from the nfl-volume-v1 model. Its P(over) is anchored to the line and has not been validated; no betting recommendation.'

export interface NflVolumeRow {
  label: string
  value: string
}

export interface NflVolumeModel {
  title: string
  aside: string
  rows: NflVolumeRow[]
  note: string
}

type VolumeLine = Pick<NflSlateLine, 'market' | 'oddsType' | 'volume'>

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

/** Goblin and demon rungs are frozen with a companion too (49e) but not shown, so the pages keep their standard-line look. */
function shownVolume(row: VolumeLine) {
  return row.market === 'receptions' && row.oddsType === 'standard' && row.volume != null ? row.volume : null
}

/** Only standard receptions lines show the companion; an absent or null field means there is nothing to show. */
export function volumeReferenceModel(row: VolumeLine): NflVolumeModel | null {
  const volume = shownVolume(row)
  if (volume === null) return null
  return {
    title: 'Volume model',
    aside: 'reference',
    rows: [
      { label: 'Projection (mean)', value: formatProjection(row.market, volume.projection) },
      { label: 'Median', value: formatProjection(row.market, volume.median) },
      { label: 'Reference gap', value: `${edgeLabel(volume.gap)} vs ${formatProjection(row.market, volume.line)} line` },
      { label: 'Chance over', value: `${percent(volume.pOver)} over · ${percent(volume.pUnder)} under · ${percent(volume.pPush)} push` },
      { label: 'Games behind it', value: String(volume.gamesInSample) },
    ],
    note: VOLUME_NOTE,
  }
}

/** One short gray line under the model value in a table row, or null. */
export function volumeTableText(row: VolumeLine): string | null {
  const volume = shownVolume(row)
  if (volume === null) return null
  return `Volume ${formatProjection(row.market, volume.projection)} · ${percent(volume.pOver)} over`
}
