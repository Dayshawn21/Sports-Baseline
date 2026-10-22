import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { NflPlayerGameLog } from '~/components/nfl/NflPlayerGameLog'
import { NflPlayerLines } from '~/components/nfl/NflPlayerLines'
import { NflPlayerFooter, NflPlayerRecord } from '~/components/nfl/NflPlayerRecord'
import { NflPlayerUsage } from '~/components/nfl/NflPlayerUsage'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useNflPlayer, useNflSlate } from '~/hooks/useNfl'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import type { NflPlayerDetail } from '~/types/nfl'
import { isNotFound } from '~/utils/httpError'
import { parseGameId } from '~/utils/nflGame'
import { FOCUS_LABELS, isNflSpecialist, playerWeekLines } from '~/utils/nflPlayer'
import './nfl-slate.css'
import './nfl-player.css'

const MISSING = '--'

function PlayerPageState({ children }: { children: ReactNode }) {
  return <div className="page-shell nfl-slate nfl-player"><div className="page-container is-wide">
    <Link className="nfl-player-crumb" to="/nfl">← NFL slate</Link>
    <PageHead title="NFL player" />
    {children}
  </div></div>
}

function NotFound() {
  return <PlayerPageState><div className="nfl-player-empty is-page">Player not found. The link may be wrong, or the player is not in the loaded NFL data.</div></PlayerPageState>
}

function injuryTag(player: NflPlayerDetail): { text: string, tone: string } {
  if (player.injuryStatus === null) {
    return { text: player.practiceStatus ?? 'No injury designation', tone: '' }
  }
  const text = player.injury ? `${player.injuryStatus} · ${player.injury}` : player.injuryStatus
  return { text, tone: player.injuryStatus === 'Out' ? 'is-out' : 'is-caution' }
}

function Availability({ player }: { player: NflPlayerDetail }) {
  const injury = injuryTag(player)
  const depth = player.depthPosition !== null && player.depthRank !== null ? `Depth: ${player.depthPosition}${player.depthRank}` : 'Not on this week\'s depth chart'
  const team = player.team === null ? 'No team (cut or retired)' : `Week ${player.week} team: ${player.team} (roster)`
  return <div className="nfl-player-tags" role="group" aria-label="Availability and roster">
    <span className="nfl-player-tag">{depth}</span>
    <span className={`nfl-player-tag ${injury.tone}`}>{injury.text}</span>
    <span className="nfl-player-tag">{team}</span>
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
  const detail = useNflPlayer(playerId)
  const slate = useNflSlate(detail.data?.season ?? null, detail.data?.week ?? null)
  useRegisterDetailTitle(detail.isSuccess && playerId !== null ? detail.data.name : null)
  if (playerId === null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <PlayerPageState><LoadingState message="Loading player..." /></PlayerPageState>
  if (detail.isError || !detail.data) return <PlayerPageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></PlayerPageState>
  const player = detail.data
  const week = slate.data && playerId !== null ? playerWeekLines(slate.data.games, playerId) : null
  return <div className="page-shell nfl-slate nfl-player"><div className="page-container is-wide">
    {week
      ? <Link className="nfl-player-crumb" to={`/nfl/game/${week.game.gameId}`}>← {week.game.awayTeam} @ {week.game.homeTeam}</Link>
      : <Link className="nfl-player-crumb" to="/nfl">← Week {player.week} slate</Link>}
    <PageHead title={player.name}
      meta={<>{[player.position, player.team].filter(Boolean).join(' · ') || 'NFL'} · {player.season} season · Week {player.week}</>}
      stats={<Chips player={player} />} />
    <Availability player={player} />
    {player.summary.games === 0 && <p className="nfl-player-note">No games yet this season. The log below shows last season.</p>}
    <div className="nfl-player-grid">
      {!isNflSpecialist(player.position) && <NflPlayerUsage player={player} />}
      <NflPlayerLines week={week} isLoading={slate.isLoading} isError={slate.isError} />
    </div>
    <NflPlayerGameLog player={player} />
    <NflPlayerRecord player={player} />
    <NflPlayerFooter player={player} />
  </div></div>
}
