import type { ModelPredictionsResponse } from '~/types/tennis'
import type { HomeStatus } from '~/utils/home'

export type RecordSport = 'tennis' | 'nfl' | 'nba' | 'nhl'

export interface HomeRecord {
  sport: RecordSport
  status: HomeStatus
  /** The published headline: the adopted-slice count, or tennis's ensemble-versus-market read. */
  label: string
  detail: string
}

const DETAIL: Record<RecordSport, string> = {
  tennis: 'Ensemble vs market, ATP+WTA',
  nfl: 'V4 forward ranking check',
  nba: 'Forward ranking check',
  nhl: 'Forward ranking check',
}

function placeholder(sport: RecordSport, status: HomeStatus): HomeRecord {
  return { sport, status, label: status === 'error' ? 'Unavailable' : '--', detail: DETAIL[sport] }
}

const NO_DATA = 'No data'

function countOf(slices: readonly { verdict: string }[], ...verdicts: string[]): number {
  return slices.filter(slice => verdicts.includes(slice.verdict)).length
}

/** NFL, NBA and NHL slices: the label counts adopted ones, and the detail names the rest so a rejected slice never reads as still accruing. */
export function rankingRecord(
  sport: 'nfl' | 'nba' | 'nhl',
  ranking: { slices: readonly { verdict: string }[] } | undefined,
  status: HomeStatus,
): HomeRecord {
  if (!ranking) return placeholder(sport, status)
  const { slices } = ranking
  const counted: [number, string][] = [
    [countOf(slices, 'reject'), 'rejected'],
    [countOf(slices, 'pass'), 'passed'],
    [countOf(slices, 'insufficient', 'accruing'), 'accruing'],
  ]
  const rest = counted.filter(([count]) => count > 0).map(([count, word]) => `${count} ${word}`)
  return {
    sport,
    status: 'ready',
    label: `${countOf(slices, 'adopt')} of ${slices.length} adopted`,
    detail: [DETAIL[sport], ...rest].join(' · '),
  }
}

const TENNIS_READ = { positive: 'Ahead of market', neutral: 'Level with market', negative: 'Behind market' } as const

/** Tennis has no adoption rule on its model page; its headline is the pooled ensemble-versus-market read, with a tie called a tie. */
export function tennisRecord(data: ModelPredictionsResponse | undefined, status: HomeStatus): HomeRecord {
  if (!data) return placeholder('tennis', status)
  const pooled = data.groups.find(group => group.group === 'ATP+WTA')
  const signal = pooled?.components.find(component => component.name === 'ensemble')?.vsMarket?.signal
  const label = pooled && pooled.n > 0 && signal ? TENNIS_READ[signal] : NO_DATA
  return { sport: 'tennis', status: 'ready', label, detail: DETAIL.tennis }
}
