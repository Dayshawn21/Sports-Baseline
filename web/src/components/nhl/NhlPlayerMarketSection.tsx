import { NhlPlayerEvidence } from '~/components/nhl/NhlPlayerEvidence'
import { NhlPlayerFormSection } from '~/components/nhl/NhlPlayerFormSection'
import { PlayerEvidence } from '~/components/shared/PlayerEvidence'
import { PlayerLinesTable, type PlayerLinesRow } from '~/components/shared/PlayerLinesTable'
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
  const rows: PlayerLinesRow[] = market.lines.map((rung, index) => {
    const note = nhlLineProbabilityNote(rung.flags)
    return {
      // A feed can store the same tier and line twice, so the position keeps the key unique.
      key: `${rung.oddsType}-${rung.line}-${index}`,
      type: ODDS_TYPE_LABELS[rung.oddsType] ?? rung.oddsType,
      line: nhlPropLineLabel(market.market, rung.line),
      gap: nhlGapLabel(rung.gap),
      pOver: <>{nhlPercentLabel(rung.pOver)}{note && <small>{note}</small>}</>,
      pUnder: nhlPercentLabel(rung.pUnder),
      trailing: [{ content: <time dateTime={rung.fetchedAt}>{nhlTimeLabel(rung.fetchedAt, true)}</time> }],
    }
  })
  return <PlayerLinesTable columns={covers ? ['gap', 'pOver', 'pUnder'] : ['gap']} trailing={['Updated (CT)']} rows={rows}
    intro={covers && <p className="nfl-player-muted">{NHL_PROBABILITY_CAPTION}.{weakNote && ` ${weakNote}`}</p>} />
}

/** One market's tab on the player page: the lines on offer beside the gray reference projection and, where the fit covers the market, a gray P(over) per line. Never a pick. */
export function NhlPlayerMarketSection({ id, player, market }: { id: string, player: NhlPlayerProps, market: NhlPlayerMarket }) {
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title">{nhlMarketLabel(market.market)}</h3>
      <span className="nfl-player-muted">{NHL_PROJECTION_CAPTION}.</span>
    </div>
    <div className="nfl-player-prop__body player-market">
      <PlayerProjectionHero hero={nhlProjectionHero(market)} />
      <NhlPlayerFormSection market={market} opponent={player.opponent} />
      <Rungs market={market} />
      <PlayerEvidence contents="Injury report, starting goalies">
        <NhlPlayerEvidence player={player} now={new Date()} />
      </PlayerEvidence>
    </div>
  </section>
}
