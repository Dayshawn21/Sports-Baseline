import {
  DetailBreakdown, DetailContext, DetailFlags, DetailGameLog, DetailLines, DetailProjection, DetailSportsbook, DetailStatus,
} from '~/components/nfl/NflPropDetailSections'
import { NflOpponentAllowed } from '~/components/nfl/NflEvidenceContext'
import type { NflSlateGame } from '~/types/nfl'
import { formatProjection, marketLabel } from '~/utils/nflLabels'
import { nflPropDetail } from '~/utils/nflPropDetail'
import type { NflPlayerWeekLine } from '~/utils/nflPlayer'
import { edgeLabel, edgePctLabel } from '~/utils/nflSignal'
import { isTargetsReference, TARGETS_REFERENCE_NOTE } from '~/utils/nflTargets'
import './nfl-prop-detail.css'

const TD = 'anytime_touchdown'

/** One prop's evidence on the player page. The game market and the usage table are the same for every prop, so the page shows them once. */
export function NflPlayerPropSection({ id, item, game }: { id: string, item: NflPlayerWeekLine, game: NflSlateGame }) {
  const { row } = item
  const detail = nflPropDetail(row, game, item.alternates, Date.now())
  const reference = isTargetsReference(row.market)
  const isTd = row.market === TD
  const gap = reference ? `${edgeLabel(row.edge)} gap` : isTd ? null : edgePctLabel(item.edgeShare)
  return <section id={id} className="nfl-player-card nfl-player-prop" aria-labelledby={`${id}-title`}>
    <div className="nfl-player-card__head">
      <h3 id={`${id}-title`} className="nfl-player-prop__title" title={reference ? TARGETS_REFERENCE_NOTE : undefined}>
        {marketLabel(row.market)}{reference ? <small>reference</small> : item.rank !== null && <small>#{item.rank}</small>}
      </h3>
      <span className="nfl-player-muted">
        {isTd ? 'Anytime' : `Line ${row.line?.toFixed(1) ?? '--'}`} · Model {formatProjection(row.market, row.projection)}{gap && ` · ${gap}`}
      </span>
    </div>
    <div className="nfl-player-prop__body">
      <DetailProjection detail={detail} />
      <DetailGameLog row={row} detail={detail} />
      <NflOpponentAllowed row={row} game={game} />
      <DetailContext detail={detail} />
      <DetailBreakdown detail={detail} />
      <DetailLines detail={detail} />
      <DetailSportsbook detail={detail} />
      <DetailStatus detail={detail} />
      <DetailFlags detail={detail} />
    </div>
  </section>
}
