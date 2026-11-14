import { useSearchParams } from 'react-router-dom'
import { FormSwitch, GameLogBars } from '~/components/nfl/NflPropDetailSections'
import { PlayerLinesTable } from '~/components/shared/PlayerLinesTable'
import type { NflOtherMarket } from '~/types/nfl'
import { formBars } from '~/utils/nflPropCards'
import { formEmptyText, formShortNote, formSample, formTitle, parseFormWindow, resolveFormWindow } from '~/utils/nflFormWindow'
import { formatProjection, marketLabel, ODDS_TYPE_LABELS } from '~/utils/nflLabels'
import { notLoadedCount, otherMarketFormRow, standardLine } from '~/utils/nflOtherMarkets'
import './nfl-prop-detail.css'

/** A stored line-only market on the player page: the line, its alternates and recent results. Reference only, so no model, gap, rank or color. */
export function NflPlayerOtherMarketSection({ id, market, opponent }: { id: string, market: NflOtherMarket, opponent: string | null }) {
  const [params] = useSearchParams()
  const row = otherMarketFormRow(market, opponent)
  const window = resolveFormWindow(row, parseFormWindow(params))
  const sample = formSample(row, window)
  const line = standardLine(market)
  const barRow = { market: market.market, line, segment: 'full_game' }
  const hasBars = formBars(sample, barRow).bars.length > 0
  const missing = notLoadedCount(market, window)
  const note = [formShortNote(row, window), missing > 0 ? `${missing} not loaded` : null].filter(Boolean).join(' · ')
  const summary = sample.average === null ? formEmptyText(row, window) : `${formatProjection(market.market, sample.average)} avg${note ? ` · ${note}` : ''}`
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title">{marketLabel(market.market)}<small>reference</small></h3>
      <span className="nfl-player-muted">{line === null ? 'No standard line' : `Line ${line.toFixed(1)}`} · Recent results only, no model comparison</span>
    </div>
    <div className="nfl-player-prop__body player-market">
      <section className="nfl-prop-detail__section">
        <div className="nfl-prop-detail__section-head"><h3>{formTitle(row, window)}</h3><span>{summary}</span></div>
        <div className="nfl-prop-detail__toolbar">
          <FormSwitch row={row} window={window} />
          {hasBars && line !== null && <span className="nfl-prop-detail__legend">Line {line.toFixed(1)}</span>}
        </div>
        <GameLogBars row={barRow} sample={sample} />
      </section>
      <PlayerLinesTable columns={[]} rows={market.lines.map((rung, index) => ({
        // A feed can store the same tier and line twice, so the position keeps the key unique.
        key: `${rung.oddsType}-${rung.line}-${index}`, type: rung.oddsType ? ODDS_TYPE_LABELS[rung.oddsType] ?? rung.oddsType : 'Standard', line: rung.line.toFixed(1),
      }))}>
        <p className="nfl-prop-detail__note">Reference only: no projection, gap or rank for this market.</p>
      </PlayerLinesTable>
    </div>
  </section>
}
