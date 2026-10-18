import { Link } from 'react-router-dom'
import PageHead from '~/components/shared/PageHead'
import type { MatchDetail, MatchPlayerDetail } from '~/types/tennis'
import { fmtStartCT } from '~/utils/format'
import { tourTone } from '~/utils/tennisSlate'
import { isFinished, matchContext, playerBadge, playerMeta, type Side } from '~/utils/tennisMatch'
import '~/components/tennis/tennis-slate.css'

function PlayerSide({ player, side, detail }: { player: MatchPlayerDetail; side: Side; detail: MatchDetail }) {
  const won = detail.winnerSide === side
  return (
    <div className={`tennis-match-side is-${side}`}>
      <span className="tennis-match-badge" aria-hidden="true">{playerBadge(player)}</span>
      <div>
        <p className="tennis-match-name">
          <Link className="tennis-name-link" to={`/tennis/player/${player.playerId}`}>{player.name}</Link>
          {won && <span className="tennis-match-won">Won</span>}
        </p>
        <div className="tennis-match-meta">{playerMeta(player, detail.surface)}</div>
      </div>
    </div>
  )
}

export default function MatchHeader({ detail }: { detail: MatchDetail }) {
  const tone = tourTone(detail.tour, detail.tourLabel)
  const finished = isFinished(detail)
  return (
    <>
      <PageHead title={`${detail.p1.name} vs ${detail.p2.name}`}
        meta={<><span className={`tennis-tour-tag${tone ? ` is-${tone}` : ''}`}>{detail.tourLabel || detail.tour}</span>{' · '}{matchContext(detail)}{' · '}
          {finished && detail.score ? `Final · ${detail.score}` : fmtStartCT(detail.startUtc) || 'Time TBA'}</>} />
      <div className="tennis-match-head" role="group" aria-label="Players">
        <PlayerSide player={detail.p1} side="p1" detail={detail} />
        <PlayerSide player={detail.p2} side="p2" detail={detail} />
      </div>
    </>
  )
}
