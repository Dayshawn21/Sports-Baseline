import { Tag } from 'antd'
import { Fragment } from 'react'
import { NbaInjuryEvidence } from '~/components/nba/NbaInjury'
import { NbaOpponentEvidence } from '~/components/nba/NbaOpponentEvidence'
import { NbaPlayerFormSection } from '~/components/nba/NbaPlayerFormSection'
import { PlayerEvidence } from '~/components/shared/PlayerEvidence'
import { PlayerProjectionHero } from '~/components/shared/PlayerProjectionHero'
import type { NbaPlayerMarket, NbaPlayerProps } from '~/types/nba'
import { ODDS_TYPE_LABELS } from '~/utils/nflLabels'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPercentText, nbaProjectionHero, nbaRungNotes } from '~/utils/nbaPlayer'
import { signedGap } from '~/utils/nbaProps'

function Rungs({ market }: { market: NbaPlayerMarket }) {
  const modelled = market.kind === 'modelled'
  const notes = nbaRungNotes(market.lines)
  return <section className="nfl-prop-detail__section">
    <div className="nfl-prop-detail__section-head"><h3>PrizePicks lines</h3></div>
    <div className="nba-player-table-wrap">
      <table className="nfl-prop-detail__table">
        <thead><tr>
          <th>Type</th><th>Line</th>
          {modelled && <><th>Gap</th><th>P(over)</th><th>P(under)</th></>}
        </tr></thead>
        <tbody>{market.lines.map((rung, index) => <Fragment key={`${rung.oddsType}-${rung.line}`}>
          <tr>
            <td><Tag>{rung.oddsType ? ODDS_TYPE_LABELS[rung.oddsType] ?? rung.oddsType : 'Standard'}</Tag></td>
            <td>{rung.line}</td>
            {modelled && <>
              <td>{rung.gap === null ? '--' : signedGap(rung.gap)}</td>
              <td>{nbaPercentText(rung.pOver)}</td>
              <td>{nbaPercentText(rung.pUnder)}</td>
            </>}
          </tr>
          {notes.perRung[index] && <tr className="nba-player-flag-row"><td colSpan={5}>{notes.perRung[index]}</td></tr>}
        </Fragment>)}</tbody>
      </table>
    </div>
    {notes.shared && <p className="nba-player-sample">{notes.shared}</p>}
  </section>
}

/** One market's tab on the player page: the gray reference projection when modelled, recent form, its lines, then the injury and opponent evidence, closed. */
export function NbaPlayerMarketSection({ id, player, market }: { id: string, player: NbaPlayerProps, market: NbaPlayerMarket }) {
  const modelled = market.kind === 'modelled'
  const hero = nbaProjectionHero(market, player.modelVersion)
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title">{nbaMarketLabel(market.market)}{!modelled && <small>reference</small>}</h3>
      <span className="nfl-player-muted">
        {modelled ? 'Reference projection only. No pick, rank, or signal.' : 'Recent results only. This market is not modelled.'}
      </span>
    </div>
    <div className="nfl-player-prop__body">
      {hero && <PlayerProjectionHero hero={hero} />}
      <NbaPlayerFormSection market={market} opponent={player.opponent} />
      <Rungs market={market} />
      <PlayerEvidence contents="Injury report, opponent allowed">
        <NbaInjuryEvidence injury={player.injury} report={player.injuryReport} startUtc={player.game?.startUtc ?? null} now={new Date()} />
        <NbaOpponentEvidence context={player.teamStats} team={player.team} market={market.market} />
      </PlayerEvidence>
    </div>
  </section>
}
