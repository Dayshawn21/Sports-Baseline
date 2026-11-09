import { Tag } from 'antd'
import { NhlPlayerEvidence } from '~/components/nhl/NhlPlayerEvidence'
import { NhlPlayerFormSection } from '~/components/nhl/NhlPlayerFormSection'
import { PlayerEvidence } from '~/components/shared/PlayerEvidence'
import { PlayerProjectionHero } from '~/components/shared/PlayerProjectionHero'
import type { NhlPlayerMarket, NhlPlayerProps } from '~/types/nhl'
import { nhlTimeLabel } from '~/utils/nhlGame'
import { nhlMarketLabel, nhlPropLineLabel } from '~/utils/nhlLineOnly'
import { ODDS_TYPE_LABELS } from '~/utils/nflLabels'
import {
  NHL_PROBABILITY_CAPTION, NHL_PROJECTION_CAPTION, nhlGapLabel, nhlLineProbabilityNote, nhlPercentLabel, nhlProbabilityNote,
} from '~/utils/nhlProjection'
import { nhlProjectionHero } from '~/utils/nhlPlayer'

function Rungs({ market }: { market: NhlPlayerMarket }) {
  const covers = market.lines.some(rung => rung.pOver !== null || nhlLineProbabilityNote(rung.flags) !== null)
  const weakNote = nhlProbabilityNote(market.market)
  return <section className="nfl-prop-detail__section">
    <div className="nfl-prop-detail__section-head"><h3>PrizePicks lines</h3></div>
    {covers && <p className="nfl-player-muted">{NHL_PROBABILITY_CAPTION}.{weakNote && ` ${weakNote}`}</p>}
    <div className="nhl-player-table-wrap">
      <table className="nfl-prop-detail__table">
        <thead><tr><th>Type</th><th>Line</th><th>Gap</th>{covers && <><th>P(over)</th><th>P(under)</th></>}<th>Updated (CT)</th></tr></thead>
        <tbody>{market.lines.map(rung => <tr key={`${rung.oddsType}-${rung.line}`}>
          <td><Tag>{ODDS_TYPE_LABELS[rung.oddsType] ?? rung.oddsType}</Tag></td>
          <td>{nhlPropLineLabel(market.market, rung.line)}</td>
          <td>{nhlGapLabel(rung.gap)}</td>
          {covers && <>
            <td>{nhlPercentLabel(rung.pOver)}{nhlLineProbabilityNote(rung.flags) && <small>{nhlLineProbabilityNote(rung.flags)}</small>}</td>
            <td>{nhlPercentLabel(rung.pUnder)}</td>
          </>}
          <td><time dateTime={rung.fetchedAt}>{nhlTimeLabel(rung.fetchedAt, true)}</time></td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>
}

/** One market's tab on the player page: the lines on offer beside the gray reference projection and, where the fit covers the market, a gray P(over) per line. Never a pick. */
export function NhlPlayerMarketSection({ id, player, market }: { id: string, player: NhlPlayerProps, market: NhlPlayerMarket }) {
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title">{nhlMarketLabel(market.market)}</h3>
      <span className="nfl-player-muted">{NHL_PROJECTION_CAPTION}.</span>
    </div>
    <div className="nfl-player-prop__body">
      <PlayerProjectionHero hero={nhlProjectionHero(market)} />
      <NhlPlayerFormSection market={market} opponent={player.opponent} />
      <Rungs market={market} />
      <PlayerEvidence contents="Injury report, starting goalies">
        <NhlPlayerEvidence player={player} now={new Date()} />
      </PlayerEvidence>
    </div>
  </section>
}
