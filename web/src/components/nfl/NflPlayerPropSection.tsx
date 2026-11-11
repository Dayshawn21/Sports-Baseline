import {
  DetailBreakdown, DetailContext, DetailFlags, DetailGameLog, DetailLines, DetailSportsbook, DetailStatus,
  DetailVolume,
} from '~/components/nfl/NflPropDetailSections'
import { NflOpponentAllowed } from '~/components/nfl/NflEvidenceContext'
import { PlayerEvidence } from '~/components/shared/PlayerEvidence'
import { PlayerProjectionHero } from '~/components/shared/PlayerProjectionHero'
import type { NflSlateGame } from '~/types/nfl'
import { marketLabel } from '~/utils/nflLabels'
import { nflProjectionHero, nflPropDetail } from '~/utils/nflPropDetail'
import type { NflPlayerWeekLine } from '~/utils/nflPlayer'
import { edgePctLabel } from '~/utils/nflSignal'
import { isTargetsReference, TARGETS_REFERENCE_NOTE } from '~/utils/nflTargets'
import './nfl-prop-detail.css'

const TD = 'anytime_touchdown'

/** One prop's evidence on the player page. The game market and the usage table are the same for every prop, so the page shows them once. */
export function NflPlayerPropSection({ id, item, game }: { id: string, item: NflPlayerWeekLine, game: NflSlateGame }) {
  const { row } = item
  const detail = nflPropDetail(row, game, item.alternates, Date.now())
  const reference = isTargetsReference(row.market)
  const isTd = row.market === TD
  // The projection block already reads the gap in units; the head keeps only the share, which it does not.
  const gapShare = reference || isTd || item.edgeShare === null ? null : `${edgePctLabel(item.edgeShare)} gap`
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title" title={reference ? TARGETS_REFERENCE_NOTE : undefined}>
        {marketLabel(row.market)}{reference && <small>reference</small>}
      </h3>
      {gapShare && <span className="nfl-player-muted">{gapShare}</span>}
    </div>
    <div className="nfl-player-prop__body">
      <PlayerProjectionHero hero={nflProjectionHero(row, detail)} />
      <DetailGameLog row={row} />
      <DetailLines detail={detail} />
      <PlayerEvidence contents="Opponent allowed, history, how it is built, sportsbooks, status">
        <NflOpponentAllowed row={row} game={game} />
        <DetailContext detail={detail} />
        <DetailBreakdown detail={detail} />
        <DetailVolume row={row} />
        <DetailSportsbook detail={detail} />
        <DetailStatus detail={detail} />
        <DetailFlags detail={detail} />
      </PlayerEvidence>
    </div>
  </section>
}
