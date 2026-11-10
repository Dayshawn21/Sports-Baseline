import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { NflPlayerContext } from '~/components/nfl/NflPlayerContext'
import { NflPlayerGameLog } from '~/components/nfl/NflPlayerGameLog'
import { NflPlayerProps } from '~/components/nfl/NflPlayerProps'
import { NflPlayerFooter, NflPlayerRecord } from '~/components/nfl/NflPlayerRecord'
import { NflPlayerUsage } from '~/components/nfl/NflPlayerUsage'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { PlayerNotFound, PlayerPageShell } from '~/components/shared/PlayerPageShell'
import { PlayerTag } from '~/components/shared/PlayerTag'
import StatChip from '~/components/shared/StatChip'
import { useNflOtherMarkets, useNflPlayer, useNflSlate } from '~/hooks/useNfl'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import type { NflPlayerDetail } from '~/types/nfl'
import { isNotFound } from '~/utils/httpError'
import { parseGameId } from '~/utils/nflGame'
import { arrivedFromBoard, FOCUS_LABELS, isNflSpecialist, playerWeekLines, playerWeekParams } from '~/utils/nflPlayer'
import { injuryTone } from '~/utils/playerPage'
import './nfl-slate.css'
import './nfl-player.css'

const MISSING = '--'

const SLATE_CRUMB = <Link className="nfl-player-crumb" to="/nfl">← NFL slate</Link>

function PlayerPageState({ children }: { children: ReactNode }) {
  return <PlayerPageShell crumb={SLATE_CRUMB} title="NFL player">{children}</PlayerPageShell>
}

function injuryText(player: NflPlayerDetail): string {
  if (player.injuryStatus === null) return player.practiceStatus ?? 'No injury designation'
  return player.injury ? `${player.injuryStatus} · ${player.injury}` : player.injuryStatus
}

function Availability({ player }: { player: NflPlayerDetail }) {
  const depth = player.depthPosition !== null && player.depthRank !== null ? `Depth: ${player.depthPosition}${player.depthRank}` : 'Not on this week\'s depth chart'
  const team = player.team === null ? 'No team (cut or retired)' : `Week ${player.week} team: ${player.team} (roster)`
  return <div className="nfl-player-tags" role="group" aria-label="Availability and roster">
    <PlayerTag>{depth}</PlayerTag>
    <PlayerTag tone={injuryTone(player.injuryStatus)}>{injuryText(player)}</PlayerTag>
    <PlayerTag>{team}</PlayerTag>
  </div>
}

function perGame(value: number | null): string {
  return value === null ? MISSING : value.toFixed(1)
}

function Chips({ player }: { player: NflPlayerDetail }) {
  const { summary } = player
  const labels = player.focusMarket ? FOCUS_LABELS[player.focusMarket] : undefined
  return <section className="page-head__stats nfl-player-stats" aria-label="Season to date">
    <StatChip value={summary.games} label={`Games ${player.season}`} />
    {labels && <StatChip value={perGame(summary.focusPerGame)} label={labels.focus} />}
    {labels && <StatChip value={perGame(summary.volumePerGame)} label={labels.volume} />}
    {!isNflSpecialist(player.position) && <StatChip value={summary.snapShare === null ? MISSING : `${Math.round(summary.snapShare * 100)}%`} label="Snap share" />}
  </section>
}

export default function NflPlayerPage() {
  const playerId = parseGameId(useParams().playerId)
  const navigate = useNavigate()
  const fromBoard = arrivedFromBoard(useLocation().state)
  const detail = useNflPlayer(playerId)
  const [params] = useSearchParams()
  // The linked week wins; the profile and game log below stay as of the current week.
  const linked = playerWeekParams(params)
  const season = linked?.season ?? detail.data?.season ?? null
  const weekNumber = linked?.week ?? detail.data?.week ?? null
  const slate = useNflSlate(season, weekNumber)
  const others = useNflOtherMarkets(playerId, season, weekNumber)
  useRegisterDetailTitle(detail.isSuccess && playerId !== null ? detail.data.name : null)
  if (playerId === null || isNotFound(detail.error)) return <PlayerNotFound crumb={SLATE_CRUMB} sport="NFL" />
  if (detail.isLoading) return <PlayerPageState><LoadingState message="Loading player..." /></PlayerPageState>
  if (detail.isError || !detail.data) return <PlayerPageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></PlayerPageState>
  const player = detail.data
  const week = slate.data && playerId !== null ? playerWeekLines(slate.data.games, playerId) : null
  const crumb = fromBoard
    ? <Link className="nfl-player-crumb" to="/nfl/board" onClick={event => { event.preventDefault(); navigate(-1) }}>← Props</Link>
    : week
    ? <Link className="nfl-player-crumb" to={`/nfl/game/${week.game.gameId}`}>← {week.game.awayTeam} @ {week.game.homeTeam}</Link>
    : <Link className="nfl-player-crumb" to="/nfl">← Week {player.week} slate</Link>
  return <PlayerPageShell crumb={crumb} title={player.name} stats={<Chips player={player} />} notice={<Availability player={player} />}
    meta={<>{[player.position, player.team].filter(Boolean).join(' · ') || 'NFL'} · {player.season} season · Week {player.week}</>}>
    {player.summary.games === 0 && <p className="nfl-player-note">No games yet this season. The log below shows last season.</p>}
    <NflPlayerProps key={playerId} week={week} others={others} weekNumber={weekNumber ?? player.week} />
    {!isNflSpecialist(player.position) && <>
      <h2 className="nfl-player-section-title">Season form <small>usage by week and recent vs season</small></h2>
      <NflPlayerUsage player={player} />
      <NflPlayerContext week={week} />
    </>}
    <NflPlayerGameLog player={player} layoutSettled={!slate.isLoading} propMarkets={[...(week?.lines.map(item => item.row.market) ?? []), ...(others.data?.markets.map(item => item.market) ?? [])]} />
    <h2 className="nfl-player-section-title">Model record <small>past PrizePicks lines, never colored</small></h2>
    <NflPlayerRecord player={player} />
    <NflPlayerFooter player={player} />
  </PlayerPageShell>
}
