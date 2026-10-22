import { Tabs } from 'antd'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { NflBestLineCard } from '~/components/nfl/NflBestLineCard'
import { NflDataGuide } from '~/components/nfl/NflDataGuide'
import { NflGameHero, NflGameMarketBlock } from '~/components/nfl/NflGameHero'
import { NflGameProps } from '~/components/nfl/NflGameProps'
import { NflGameContext } from '~/components/nfl/NflGameContext'
import { NflGameAvailability, NflGameSidebar } from '~/components/nfl/NflGameSidebar'
import { NflLineMovementChart } from '~/components/nfl/NflLineMovementChart'
import { NflTeamStatsMatchup } from '~/components/nfl/NflTeamStatsMatchup'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import { useNflGame, useNflGameNotes, useNflSlate } from '~/hooks/useNfl'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { isNotFound } from '~/utils/httpError'
import { kickoffLabel, parseGameId } from '~/utils/nflGame'
import './nfl-slate.css'
import './nfl-prop-board.css'
import './nfl-game.css'

function BackLink({ week }: { week: number | null }) {
  return <Link className="nfl-game-crumb" to="/nfl">← {week === null ? 'NFL slate' : `Week ${week} slate`}</Link>
}

function GamePageState({ children }: { children: ReactNode }) {
  return <div className="page-shell nfl-slate nfl-game"><div className="page-container is-wide">
    <BackLink week={null} />
    <PageHead title="NFL game" />
    {children}
  </div></div>
}

function NotFound() {
  return <GamePageState><div className="nfl-game-empty is-page">Game not found. It may not be a loaded regular-season game, or the link is wrong.</div></GamePageState>
}

export default function NflGamePage() {
  const gameId = parseGameId(useParams().gameId)
  const detail = useNflGame(gameId)
  const slate = useNflSlate(detail.data?.season ?? null, detail.data?.week ?? null)
  const notes = useNflGameNotes(detail.data?.season ?? null, detail.data?.week ?? null)
  useRegisterDetailTitle(detail.isSuccess && gameId !== null ? `${detail.data.awayTeam} @ ${detail.data.homeTeam}` : null)
  if (gameId === null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <GamePageState><LoadingState message="Loading game..." /></GamePageState>
  if (detail.isError || !detail.data) return <GamePageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></GamePageState>
  const game = slate.data?.games.find(item => item.gameId === gameId) ?? null
  const gameNotes = notes.data?.games.find(item => item.gameId === gameId)
  return <div className="page-shell nfl-slate nfl-game"><div className="page-container is-wide">
    <BackLink week={detail.data.week} />
    <PageHead title={`${detail.data.awayTeam} @ ${detail.data.homeTeam}`}
      meta={<>{detail.data.season} season · Week {detail.data.week} · {kickoffLabel(detail.data.startUtc)} · {detail.data.status}</>} />
    <NflGameHero detail={detail.data} game={game} />
    <NflDataGuide />
    <Tabs key={gameId} className="nfl-game-tabs" defaultActiveKey="props" destroyOnHidden
      aria-label="Game sections" animated={false}
      items={[
        { key: 'matchup', label: 'Matchup', children: <div className="nfl-game-layout">
          <div className="nfl-game-main">
            {slate.isLoading && <LoadingState message="Loading market..." />}
            {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
            {game && <NflGameMarketBlock game={game} notes={gameNotes} />}
            {detail.data.status === 'scheduled' && gameNotes && <NflBestLineCard bestLine={gameNotes.bestLine} homeTeam={detail.data.homeTeam} awayTeam={detail.data.awayTeam} />}
            <NflLineMovementChart detail={detail.data} />
            {gameNotes && <NflTeamStatsMatchup notes={gameNotes} />}
            <NflGameContext game={detail.data} notesContext={gameNotes?.matchupContext} section="matchup" />
            <NflGameAvailability notes={gameNotes} isLoading={notes.isLoading} isError={notes.isError} />
          </div>
          <NflGameSidebar notes={gameNotes} isLoading={notes.isLoading} isError={notes.isError} />
        </div> },
        { key: 'props', label: 'Player Props', children: <div className="nfl-game-main">
          {slate.isLoading && <LoadingState message="Loading player props..." />}
          {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
          {game && slate.data && <NflGameProps games={slate.data.games} game={game} />}
          {slate.isSuccess && !game && <p className="nfl-game-empty">No player props stored for this game.</p>}
          <NflGameContext game={detail.data} section="usage" />
        </div> },
      ]} />
  </div></div>
}
