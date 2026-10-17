import { Link, useParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PlayerEloCard from '~/components/tennis/player/PlayerEloCard'
import PlayerHeader from '~/components/tennis/player/PlayerHeader'
import PlayerMatchLog from '~/components/tennis/player/PlayerMatchLog'
import PlayerServeReturn from '~/components/tennis/player/PlayerServeReturn'
import PlayerSidebar from '~/components/tennis/player/PlayerSidebar'
import { usePlayerDetail, usePlayerMatches } from '~/hooks/useTennisPlayer'
import { isNotFound } from '~/utils/httpError'
import { parsePlayerId } from '~/utils/tennisPlayer'
import './tennis-match.css'
import './tennis-player.css'

function BackLink() {
  return <Link className="tennis-match-crumb" to="/">← Tennis slate</Link>
}

function NotFound() {
  return (
    <div className="page-shell tennis-player"><div className="page-container is-wide">
      <BackLink />
      <div className="tennis-match-empty is-page">
        That player is not in the database. The link may be wrong, or the player was merged into another on re-ingest.
      </div>
    </div></div>
  )
}

export default function TennisPlayerPage() {
  const playerId = parsePlayerId(useParams().playerId)
  const detail = usePlayerDetail(playerId)
  const matches = usePlayerMatches(playerId)

  if (playerId == null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <LoadingState message="Loading player..." />
  if (detail.isError || !detail.data) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />

  return (
    <div className="page-shell tennis-player"><div className="page-container is-wide">
      <BackLink />
      <PlayerHeader player={detail.data} now={new Date()} />
      <div className="tennis-player-layout">
        <section className="tennis-player-main">
          <PlayerEloCard player={detail.data} />
          <PlayerServeReturn playerId={detail.data.playerId} nextSurface={detail.data.nextMatch?.surface} />
          <PlayerMatchLog query={matches} />
        </section>
        <PlayerSidebar player={detail.data} matches={matches} />
      </div>
    </div></div>
  )
}
