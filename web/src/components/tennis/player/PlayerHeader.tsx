import { Link } from 'react-router-dom'
import PageHead from '~/components/shared/PageHead'
import type { PlayerDetail } from '~/types/tennis'
import { fmtStartCT } from '~/utils/format'
import { ageOn } from '~/utils/tennisPlayer'
import { tourTone } from '~/utils/tennisSlate'
import '~/components/tennis/tennis-slate.css'

const HANDS = { R: 'Right-handed', L: 'Left-handed' }

function NextMatch({ next }: { next: PlayerDetail['nextMatch'] }) {
  if (!next) return <div className="tennis-player-next"><div className="tennis-player-next__label">No upcoming match</div></div>
  const event = [next.tournament, next.round].filter(Boolean).join(' ')
  return (
    <div className="tennis-player-next">
      <div className="tennis-player-next__label">Next match</div>
      <Link to={`/tennis/match/${next.matchId}`}>vs {next.opponentName}{event && ` · ${event}`}</Link>
      <div className="tennis-player-next__time">{fmtStartCT(next.startUtc) || next.matchDate}</div>
    </div>
  )
}

export default function PlayerHeader({ player, now }: { player: PlayerDetail, now: Date }) {
  const tone = tourTone(player.tour)
  const age = ageOn(player.birthDate, now)
  const meta = [
    player.rank != null ? `#${player.rank}` : null,
    player.hand ? HANDS[player.hand] : null,
    player.country,
    age != null ? `age ${age}` : null,
  ].filter(Boolean)
  return (
    <PageHead title={player.name}
      meta={<><span className={`tennis-tour-tag${tone ? ` is-${tone}` : ''}`}>{player.tour}</span>
        {meta.length > 0 && <> · {meta.join(' · ')}</>}</>}
      actions={<NextMatch next={player.nextMatch} />} />
  )
}
