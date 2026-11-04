import { Tag } from 'antd'
import { NhlPlayerEvidence } from '~/components/nhl/NhlPlayerEvidence'
import { NhlPlayerFormSection } from '~/components/nhl/NhlPlayerFormSection'
import type { NhlPlayerMarket, NhlPlayerProps } from '~/types/nhl'
import { nhlTimeLabel } from '~/utils/nhlGame'
import { nhlMarketLabel, nhlPropLineLabel } from '~/utils/nhlLineOnly'
import { ODDS_TYPE_LABELS } from '~/utils/nflLabels'
import { NHL_PROJECTION_CAPTION, nhlGapLabel, nhlProjectionNote, nhlProjectionValue } from '~/utils/nhlProjection'

function Rungs({ market }: { market: NhlPlayerMarket }) {
  return <section className="nfl-prop-detail__section">
    <div className="nfl-prop-detail__section-head"><h3>PrizePicks lines</h3></div>
    <div className="nhl-player-table-wrap">
      <table className="nfl-prop-detail__table">
        <thead><tr><th>Type</th><th>Line</th><th>Gap</th><th>Updated (CT)</th></tr></thead>
        <tbody>{market.lines.map(rung => <tr key={`${rung.oddsType}-${rung.line}`}>
          <td><Tag>{ODDS_TYPE_LABELS[rung.oddsType] ?? rung.oddsType}</Tag></td>
          <td>{nhlPropLineLabel(market.market, rung.line)}</td>
          <td>{nhlGapLabel(rung.gap)}</td>
          <td><time dateTime={rung.fetchedAt}>{nhlTimeLabel(rung.fetchedAt, true)}</time></td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>
}

/** One market's tab on the player page: the lines on offer beside the gray reference projection. No probability or pick. */
export function NhlPlayerMarketSection({ id, player, market }: { id: string, player: NhlPlayerProps, market: NhlPlayerMarket }) {
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title">{nhlMarketLabel(market.market)}</h3>
      <span className="nfl-player-muted">
        Projection {nhlProjectionValue(market.projection)}{nhlProjectionNote(market.projection) && ` (${nhlProjectionNote(market.projection)})`}. {NHL_PROJECTION_CAPTION}.
      </span>
    </div>
    <div className="nfl-player-prop__body">
      <NhlPlayerFormSection market={market} opponent={player.opponent} />
      <Rungs market={market} />
      <NhlPlayerEvidence player={player} now={new Date()} />
    </div>
  </section>
}
