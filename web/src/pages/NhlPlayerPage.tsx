import type { ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { NhlPlayerPropTabs } from '~/components/nhl/NhlPlayerPropTabs'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { PlayerNotFound, PlayerPageShell } from '~/components/shared/PlayerPageShell'
import { useNhlPlayerProps } from '~/hooks/useNhl'
import type { NhlPlayerProps } from '~/types/nhl'
import { isNotFound } from '~/utils/httpError'
import { nhlContextSource } from '~/utils/nhlContext'
import { parseNhlGameId } from '~/utils/nhlGame'
import { nhlPlayerInjuryReport, nhlPlayerStatus } from '~/utils/nhlPlayer'
import './nfl-slate.css'
import './nfl-player.css'
import './nhl-game.css'
import './nhl-player.css'

const DATE_PARAM = /^\d{4}-\d{2}-\d{2}$/

const SLATE_CRUMB = <Link className="nfl-player-crumb" to="/nhl">← NHL slate</Link>

function PlayerPageState({ children }: { children: ReactNode }) {
  return <PlayerPageShell sportClass="nhl-player" crumb={SLATE_CRUMB} title="NHL player">{children}</PlayerPageShell>
}

function Crumb({ player }: { player: NhlPlayerProps }) {
  return player.game
    ? <Link className="nfl-player-crumb" to={`/nhl/game/${player.game.gameId}`}>← {player.game.awayTeam} @ {player.game.homeTeam}</Link>
    : <Link className="nfl-player-crumb" to={`/nhl?date=${player.date}`}>← NHL slate</Link>
}

function InjuryLine({ player }: { player: NhlPlayerProps }) {
  const freshness = nhlContextSource(nhlPlayerInjuryReport(player.injury), player.game?.startUtc ?? null, new Date()).freshness
  const entry = player.injury.entry
  if (!entry || freshness === 'unavailable') return null
  return <div className="nfl-player-tags" role="group" aria-label="Injury report">
    <span className="nhl-player-injury-tag">{entry.status}{freshness === 'stale' ? ' (stale)' : ''}</span>
  </div>
}

export default function NhlPlayerPage() {
  const playerId = parseNhlGameId(useParams().playerId)
  const [params] = useSearchParams()
  const asked = params.get('date')
  const date = asked !== null && DATE_PARAM.test(asked) ? asked : null
  const detail = useNhlPlayerProps(playerId, date)
  useRegisterDetailTitle(detail.isSuccess && playerId !== null ? detail.data.name : null)
  if (playerId === null || isNotFound(detail.error)) return <PlayerNotFound sportClass="nhl-player" crumb={SLATE_CRUMB} sport="NHL" />
  if (detail.isLoading) return <PlayerPageState><LoadingState message="Loading player..." /></PlayerPageState>
  if (detail.isError || !detail.data) return <PlayerPageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></PlayerPageState>
  const player = detail.data
  return <PlayerPageShell sportClass="nhl-player" crumb={<Crumb player={player} />} title={player.name} meta={nhlPlayerStatus(player)} notice={<InjuryLine player={player} />}>
    <NhlPlayerPropTabs key={player.playerId} player={player} />
    {player.markets.length === 0 && <div className="nfl-player-empty">
      {player.name} has no prop lines on {player.date}. <Link to={`/nhl?date=${player.date}`}>Open the NHL slate for that date</Link>.
    </div>}
  </PlayerPageShell>
}
