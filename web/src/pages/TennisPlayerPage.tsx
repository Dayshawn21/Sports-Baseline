import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import PlayerEloCard from '~/components/tennis/player/PlayerEloCard'
import PlayerHeader from '~/components/tennis/player/PlayerHeader'
import PlayerMatchLog from '~/components/tennis/player/PlayerMatchLog'
import PlayerServeReturn from '~/components/tennis/player/PlayerServeReturn'
import PlayerSidebar from '~/components/tennis/player/PlayerSidebar'
import { usePlayerDetail, usePlayerMatches } from '~/hooks/useTennisPlayer'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { isNotFound } from '~/utils/httpError'
import { parsePlayerId } from '~/utils/tennisPlayer'
import './tennis-match.css'
import './tennis-player.css'

function BackLink() {
  return <Link className="tennis-match-crumb" to="/">← Tennis slate</Link>
}

function PlayerPageState({ children }: { children: ReactNode }) {
  return (
    <div className="page-shell tennis-player"><div className="page-container is-wide">
      <BackLink />
      <PageHead title="Tennis player" />
      {children}
    </div></div>
  )
}

function NotFound() {
  return <PlayerPageState><div className="tennis-match-empty is-page">
    That player is not in the database. The link may be wrong, or the player was merged into another on re-ingest.
  </div></PlayerPageState>
}

export default function TennisPlayerPage() {
  const playerId = parsePlayerId(useParams().playerId)
  const detail = usePlayerDetail(playerId)
  const matches = usePlayerMatches(playerId)
  useRegisterDetailTitle(detail.isSuccess && playerId !== null ? detail.data.name : null)

  if (playerId == null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <PlayerPageState><LoadingState message="Loading player..." /></PlayerPageState>
  if (detail.isError || !detail.data) return <PlayerPageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></PlayerPageState>

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
