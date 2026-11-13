import { NbaInjuryEvidence } from '~/components/nba/NbaInjury'
import { NbaOpponentEvidence } from '~/components/nba/NbaOpponentEvidence'
import { NbaPlayerFormSection } from '~/components/nba/NbaPlayerFormSection'
import { NbaTeammateSplitSection } from '~/components/nba/NbaTeammateSplitSection'
import { PlayerEvidence } from '~/components/shared/PlayerEvidence'
import { PlayerLinesTable, type PlayerLinesRow } from '~/components/shared/PlayerLinesTable'
import { PlayerProjectionHero } from '~/components/shared/PlayerProjectionHero'
import type { NbaPlayerMarket, NbaPlayerProps } from '~/types/nba'
import { ODDS_TYPE_LABELS } from '~/utils/nflLabels'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPercentText, nbaProjectionHero, nbaRungNotes } from '~/utils/nbaPlayer'
import { signedGap } from '~/utils/nbaProps'

function Rungs({ market }: { market: NbaPlayerMarket }) {
  const modelled = market.kind === 'modelled'
  const notes = nbaRungNotes(market.lines)
  const rows: PlayerLinesRow[] = market.lines.map((rung, index) => ({
    key: `${rung.oddsType}-${rung.line}`,
    type: rung.oddsType ? ODDS_TYPE_LABELS[rung.oddsType] ?? rung.oddsType : 'Standard',
    line: String(rung.line),
    gap: rung.gap === null ? '--' : signedGap(rung.gap),
    pOver: nbaPercentText(rung.pOver),
    pUnder: nbaPercentText(rung.pUnder),
    note: notes.perRung[index],
  }))
  return <PlayerLinesTable columns={modelled ? ['gap', 'pOver', 'pUnder'] : []} rows={rows}>
    {notes.shared && <p className="nba-player-sample">{notes.shared}</p>}
  </PlayerLinesTable>
}

/** One market's tab on the player page: the gray reference projection when modelled, recent form, its lines, then the injury and opponent evidence, closed. */
export function NbaPlayerMarketSection({ id, player, market }: { id: string, player: NbaPlayerProps, market: NbaPlayerMarket }) {
  const modelled = market.kind === 'modelled'
  const hero = nbaProjectionHero(market)
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
      <NbaTeammateSplitSection split={player.teammateSplit} market={market} />
      <Rungs market={market} />
      <PlayerEvidence contents="Injury report, opponent allowed">
        <NbaInjuryEvidence injury={player.injury} report={player.injuryReport} startUtc={player.game?.startUtc ?? null} now={new Date()} />
        <NbaOpponentEvidence context={player.teamStats} team={player.team} market={market.market} />
      </PlayerEvidence>
    </div>
  </section>
}
