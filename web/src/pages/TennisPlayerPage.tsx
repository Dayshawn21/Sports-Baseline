import type { ReactNode } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { PlayerPageShell } from '~/components/shared/PlayerPageShell'
import PlayerEloCard from '~/components/tennis/player/PlayerEloCard'
import { playerHead } from '~/components/tennis/player/PlayerHeader'
import PlayerPropTabs from '~/components/tennis/player/PlayerPropTabs'
import PlayerMatchLog from '~/components/tennis/player/PlayerMatchLog'
import PlayerServeReturn from '~/components/tennis/player/PlayerServeReturn'
import PlayerModelRecord, { PlayerIdentityFooter } from '~/components/tennis/player/PlayerSidebar'
import { usePlayerDetail, usePlayerMatches } from '~/hooks/useTennisPlayer'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { isNotFound } from '~/utils/httpError'
import { parsePlayerId } from '~/utils/tennisPlayer'
import { playerPageOrigin } from '~/utils/tennisPlayerProps'
import './tennis-match.css'
import './tennis-player.css'

function BackLink() {
  const origin = playerPageOrigin(useLocation().state)
  return <Link className="tennis-match-crumb" to={origin?.path ?? '/tennis'}>← {origin?.label ?? 'Tennis slate'}</Link>
}

function PlayerPageState({ children }: { children: ReactNode }) {
  return <PlayerPageShell sportClass="tennis-player" crumb={<BackLink />} title="Tennis player">{children}</PlayerPageShell>
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

  const head = playerHead(detail.data, new Date())
  return (
    <PlayerPageShell sportClass="tennis-player" crumb={<BackLink />} title={head.title} meta={head.meta} actions={head.actions}>
      <PlayerPropTabs playerId={detail.data.playerId} playerName={detail.data.name} />
      <h2 className="nfl-player-section-title">Season form <small>ELO, serve and return</small></h2>
      <PlayerEloCard player={detail.data} />
      <PlayerServeReturn playerId={detail.data.playerId} nextSurface={detail.data.nextMatch?.surface} />
      <PlayerMatchLog query={matches} />
      <h2 className="nfl-player-section-title">Model record <small>52-week record and settled props</small></h2>
      <PlayerModelRecord player={detail.data} matches={matches} />
      <PlayerIdentityFooter player={detail.data} />
    </PlayerPageShell>
  )
}
