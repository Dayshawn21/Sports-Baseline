import { useSearchParams } from 'react-router-dom'
import { FormSwitch, GameLogBars } from '~/components/nfl/NflPropDetailSections'
import type { NhlPlayerMarket } from '~/types/nhl'
import { formBarLabel, formEmptyText, formSample, formShortNote, formTitle, parseFormWindow, resolveFormWindow } from '~/utils/nflFormWindow'
import { formBars } from '~/utils/nflPropCards'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { NHL_HISTORY_FROM_YEAR, NHL_SEASON_START_MONTH, nhlChartLine, nhlFormRow, nhlNotLoadedCount, nhlSampleNote } from '~/utils/nhlPlayer'

/** The recent form of one market: bars against the standard line with the window switch, from the shared form helpers. Display only. */
export function NhlPlayerFormSection({ market, opponent }: { market: NhlPlayerMarket, opponent: string | null }) {
  const [params] = useSearchParams()
  const row = nhlFormRow(market, opponent)
  const window = resolveFormWindow(row, parseFormWindow(params))
  const sample = formSample(row, window)
  const line = nhlChartLine(market)
  const barRow = { market: market.market, line, segment: 'full_game' }
  const hasBars = formBars(sample, barRow).bars.length > 0
  const missing = nhlNotLoadedCount(market, window)
  const note = [formShortNote(row, window), missing > 0 ? `${missing} not loaded` : null, nhlSampleNote(market)].filter(Boolean).join(' · ')
  const summary = sample.average === null
    ? formEmptyText(row, window, NHL_HISTORY_FROM_YEAR)
    : `${formBarLabel(sample.average)} avg${note ? ` · ${note}` : ''}`
  return <section className="nfl-prop-detail__section" aria-label={`${nhlMarketLabel(market.market)} recent form`}>
    <div className="nfl-prop-detail__section-head"><h3>{formTitle(row, window)}</h3><span>{summary}</span></div>
    <div className="nfl-prop-detail__toolbar">
      <FormSwitch row={row} window={window} />
      {hasBars && line !== null && <span className="nfl-prop-detail__legend">Line {line}</span>}
    </div>
    <GameLogBars row={barRow} sample={sample} seasonStartMonth={NHL_SEASON_START_MONTH} />
  </section>
}
