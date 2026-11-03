import type { ModelPredictionsResponse } from '~/types/tennis'
import type { HomeStatus } from '~/utils/home'
import { ensembleVerdictText } from '~/utils/trackRecord'

export type RecordSport = 'tennis' | 'nfl' | 'nba'

export interface HomeRecord {
  sport: RecordSport
  status: HomeStatus
  /** The published headline: an adopted-slice count, "Accruing", or tennis's ensemble-versus-market read. */
  label: string
  detail: string
}

const DETAIL: Record<RecordSport, string> = {
  tennis: 'Ensemble vs market, ATP+WTA',
  nfl: 'V4 forward ranking check',
  nba: 'Forward ranking check',
}

function placeholder(sport: RecordSport, status: HomeStatus): HomeRecord {
  return { sport, status, label: status === 'error' ? 'Unavailable' : '--', detail: DETAIL[sport] }
}

/** NFL and NBA: the 27j-style slices; "Accruing" until a rule has adopted one, never a pick signal. */
export function rankingRecord(
  sport: 'nfl' | 'nba',
  ranking: { slices: readonly { verdict: string }[] } | undefined,
  status: HomeStatus,
): HomeRecord {
  if (!ranking) return placeholder(sport, status)
  const adopted = ranking.slices.filter(slice => slice.verdict === 'adopt').length
  const label = adopted === 0 ? 'Accruing' : `${adopted} of ${ranking.slices.length} adopted`
  return { sport, status: 'ready', label, detail: DETAIL[sport] }
}

/** Tennis has no adoption rule on its model page; its headline is the pooled ensemble-versus-market read. */
export function tennisRecord(data: ModelPredictionsResponse | undefined, status: HomeStatus): HomeRecord {
  if (!data) return placeholder('tennis', status)
  const pooled = data.groups.find(group => group.group === 'ATP+WTA')
  return { sport: 'tennis', status: 'ready', label: ensembleVerdictText(pooled), detail: DETAIL.tennis }
}
