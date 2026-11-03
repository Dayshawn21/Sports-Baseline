import { useSearchParams } from 'react-router-dom'
import { FormSwitch, GameLogBars } from '~/components/nfl/NflPropDetailSections'
import type { NbaPlayerMarket } from '~/types/nba'
import { nbaMarketLabel, nbaRecentValueLabel } from '~/utils/nbaLineOnly'
import { NBA_HISTORY_FROM_YEAR, NBA_SEASON_START_MONTH, nbaChartLine, nbaFormRow, nbaNotLoadedCount } from '~/utils/nbaPlayer'
import { formBarLabel, formDateText, formEmptyText, formHistoryDate, formSample, formShortNote, formTitle, parseFormWindow, resolveFormWindow } from '~/utils/nflFormWindow'
import { formBars } from '~/utils/nflPropCards'

const DOUBLE_DOUBLE = 'double_double'

/** A double-double game is a yes or no, so it is a dated list rather than bars against a line. */
function YesNoList({ sample }: { sample: ReturnType<typeof formSample> }) {
  const now = new Date()
  return <ul className="nba-player-yesno" aria-label={`${sample.values.length} games`}>
    {sample.values.map((game, index) => <li key={index}>
      <span>{formDateText(formHistoryDate(game.gameDate, now, NBA_SEASON_START_MONTH)) ?? '--'}</span>
      <span>vs {game.opponentTeam ?? '--'}</span>
      <b>{nbaRecentValueLabel(DOUBLE_DOUBLE, game.value)}</b>
    </li>)}
  </ul>
}

/** The recent form of one market: bars against the standard line with the window switch, from the shared form helpers. Display only. */
export function NbaPlayerFormSection({ market, opponent }: { market: NbaPlayerMarket, opponent: string | null }) {
  const [params] = useSearchParams()
  const row = nbaFormRow(market, opponent)
  const window = resolveFormWindow(row, parseFormWindow(params))
  const sample = formSample(row, window)
  const line = nbaChartLine(market)
  const barRow = { market: market.market, line, segment: 'full_game' }
  const doubleDouble = market.market === DOUBLE_DOUBLE
  const hasBars = !doubleDouble && formBars(sample, barRow).bars.length > 0
  const missing = nbaNotLoadedCount(market, window)
  const note = [formShortNote(row, window), missing > 0 ? `${missing} not loaded` : null].filter(Boolean).join(' · ')
  const yes = sample.values.filter(game => game.value >= 1).length
  const summary = sample.average === null
    ? formEmptyText(row, window, NBA_HISTORY_FROM_YEAR)
    : `${doubleDouble ? `${yes} of ${sample.values.length} yes` : `${formBarLabel(sample.average)} avg`}${note ? ` · ${note}` : ''}`
  return <section className="nfl-prop-detail__section" aria-label={`${nbaMarketLabel(market.market)} recent form`}>
    <div className="nfl-prop-detail__section-head"><h3>{formTitle(row, window)}</h3><span>{summary}</span></div>
    <div className="nfl-prop-detail__toolbar">
      <FormSwitch row={row} window={window} />
      {hasBars && line !== null && <span className="nfl-prop-detail__legend">Line {line}</span>}
    </div>
    {doubleDouble ? <YesNoList sample={sample} /> : <GameLogBars row={barRow} sample={sample} seasonStartMonth={NBA_SEASON_START_MONTH} />}
  </section>
}
