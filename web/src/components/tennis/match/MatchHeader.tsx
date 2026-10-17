import { Link } from 'react-router-dom'
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
        <h1 className="tennis-match-name">
          <Link className="tennis-name-link" to={`/tennis/player/${player.playerId}`}>{player.name}</Link>
          {won && <span className="tennis-match-won">Won</span>}
        </h1>
        <div className="tennis-match-meta">{playerMeta(player, detail.surface)}</div>
      </div>
    </div>
  )
}

export default function MatchHeader({ detail }: { detail: MatchDetail }) {
  const tone = tourTone(detail.tour, detail.tourLabel)
  const finished = isFinished(detail)
  return (
    <header className="tennis-match-head">
      <PlayerSide player={detail.p1} side="p1" detail={detail} />
      <div className="tennis-match-center">
        <span className={`tennis-tour-tag${tone ? ` is-${tone}` : ''}`}>{detail.tourLabel || detail.tour}</span>
        <div className="tennis-match-context">{matchContext(detail)}</div>
        {finished && detail.score
          ? <div className="tennis-match-score">Final · {detail.score}</div>
          : <div className="tennis-match-time">{fmtStartCT(detail.startUtc) || 'Time TBA'}</div>}
      </div>
      <PlayerSide player={detail.p2} side="p2" detail={detail} />
    </header>
  )
}
