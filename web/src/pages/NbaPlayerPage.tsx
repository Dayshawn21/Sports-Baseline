import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { NbaInjuryTag } from '~/components/nba/NbaInjury'
import { NbaPlayerPropTabs } from '~/components/nba/NbaPlayerPropTabs'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import { useNbaPlayerProps } from '~/hooks/useNba'
import type { NbaPlayerProps } from '~/types/nba'
import { isNotFound } from '~/utils/httpError'
import { parseGameId } from '~/utils/nbaGame'
import { nbaInjuryFreshness } from '~/utils/nbaInjuries'
import { nbaPlayerStatus } from '~/utils/nbaPlayer'
import { arrivedFromBoard } from '~/utils/nflPlayer'
import './nfl-slate.css'
import './nfl-player.css'
import './nba-player.css'

const DATE_PARAM = /^\d{4}-\d{2}-\d{2}$/

function PlayerPageState({ children }: { children: ReactNode }) {
  return <div className="page-shell nfl-slate nfl-player nba-player"><div className="page-container is-wide">
    <Link className="nfl-player-crumb" to="/nba">← NBA slate</Link>
    <PageHead title="NBA player" />
    {children}
  </div></div>
}

function NotFound() {
  return <PlayerPageState><div className="nfl-player-empty is-page">Player not found. The link may be wrong, or the player is not in the loaded NBA data.</div></PlayerPageState>
}

/** A board arrival goes back one step, so the board returns on its own date and market; otherwise the game page, or the board for a player with no game. */
function Crumb({ player }: { player: NbaPlayerProps }) {
  const navigate = useNavigate()
  const board = `/nba/board?date=${player.date}`
  if (arrivedFromBoard(useLocation().state)) {
    return <Link className="nfl-player-crumb" to={board} onClick={event => { event.preventDefault(); navigate(-1) }}>← NBA props</Link>
  }
  return player.game
    ? <Link className="nfl-player-crumb" to={`/nba/game/${player.game.gameId}`}>← {player.game.awayTeam} @ {player.game.homeTeam}</Link>
    : <Link className="nfl-player-crumb" to={board}>← NBA props</Link>
}

function InjuryLine({ player }: { player: NbaPlayerProps }) {
  const freshness = nbaInjuryFreshness(player.injuryReport, player.game?.startUtc ?? null, new Date())
  if (!player.injury || freshness === 'unavailable') return null
  return <div className="nfl-player-tags" role="group" aria-label="Injury report">
    <NbaInjuryTag injury={player.injury} freshness={freshness} />
  </div>
}

export default function NbaPlayerPage() {
  const playerId = parseGameId(useParams().playerId)
  const [params] = useSearchParams()
  const asked = params.get('date')
  const date = asked !== null && DATE_PARAM.test(asked) ? asked : null
  const detail = useNbaPlayerProps(playerId, date)
  useRegisterDetailTitle(detail.isSuccess && playerId !== null ? detail.data.name : null)
  if (playerId === null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <PlayerPageState><LoadingState message="Loading player..." /></PlayerPageState>
  if (detail.isError || !detail.data) return <PlayerPageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></PlayerPageState>
  const player = detail.data
  return <div className="page-shell nfl-slate nfl-player nba-player"><div className="page-container is-wide">
    <Crumb player={player} />
    <PageHead title={player.name} meta={nbaPlayerStatus(player)} />
    <InjuryLine player={player} />
    <NbaPlayerPropTabs key={player.playerId} player={player} />
    {player.markets.length === 0 && <div className="nfl-player-empty">
      {player.name} has no prop lines on {player.date}. <Link to={`/nba/board?date=${player.date}`}>Open the NBA props board for that date</Link>.
    </div>}
  </div></div>
}
