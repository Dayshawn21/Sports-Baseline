import type { NflHistorySample } from '~/types/nfl'
import type { PropLine, PropReasonRecentValue } from '~/types/tennis'
import { tennisFormSample } from '~/utils/tennisPlayerProps'
import { lineNumber } from '~/utils/tennisPropBoard'
import type { RecentStatBar } from '~/utils/tennisPropCards'

/**
 * Whether a board row can open the Why over / Why under panel: a stored
 * PrizePicks line with a number. Rows the browser builds (moneyline, win a set)
 * carry negative ids and another source, and DraftKings is a later item.
 */
export function hasReasons(row: Pick<PropLine, 'id' | 'source' | 'line'>): boolean {
  return row.source === 'prizepicks' && row.id > 0 && lineNumber(row) != null
}

/** The response's oldest-first values as the sample the shared form chart draws. */
export function reasonsChartSample(recent: PropReasonRecentValue[], line: number): NflHistorySample {
  const bars: RecentStatBar[] = recent.map(item => ({
    matchDate: item.matchDate,
    opponentName: item.opponentName,
    value: item.value,
    vsLine: item.value > line ? 'above' : item.value < line ? 'below' : 'push',
  }))
  return tennisFormSample(bars)
}
