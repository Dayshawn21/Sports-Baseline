import { Tabs } from 'antd'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { NhlGameHero, NhlGameMarket } from '~/components/nhl/NhlGameHero'
import { NhlLineOnlyProps } from '~/components/nhl/NhlLineOnlyProps'
import { NflLineMovementChart as LineMovementChart } from '~/components/nfl/NflLineMovementChart'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import { useNhlGame } from '~/hooks/useNhl'
import { isNotFound } from '~/utils/httpError'
import { nhlGameState, nhlPuckDropLabel, parseNhlGameId } from '~/utils/nhlGame'
import './nfl-slate.css'
import './nfl-game.css'
import './nhl-game.css'

function BackLink({ date }: { date: string | null }) {
  return <Link className="nfl-game-crumb" to={date === null ? '/nhl' : `/nhl?date=${date}`}>Back to NHL slate</Link>
}

function GamePageState({ children }: { children: ReactNode }) {
  return <div className="page-shell nfl-slate nfl-game nhl-game"><div className="page-container is-wide">
    <BackLink date={null} /><PageHead title="NHL game" />{children}
  </div></div>
}

export default function NhlGamePage() {
  const gameId = parseNhlGameId(useParams().gameId)
  const detail = useNhlGame(gameId)
  useRegisterDetailTitle(detail.isSuccess && gameId !== null ? `${detail.data.awayTeam} @ ${detail.data.homeTeam}` : null)
  if (gameId === null || isNotFound(detail.error)) return <GamePageState>
    <p className="nfl-game-empty is-page">Game not found. Check the link or return to the NHL slate.</p>
  </GamePageState>
  if (detail.isLoading) return <GamePageState><LoadingState message="Loading NHL game..." /></GamePageState>
  if (detail.isError || !detail.data) return <GamePageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></GamePageState>
  const game = detail.data
  const state = nhlGameState(game, new Date())
  return <div className="page-shell nfl-slate nfl-game nhl-game"><div className="page-container is-wide">
    <BackLink date={game.gameDate} />
    <PageHead title={`${game.awayTeam} @ ${game.homeTeam}`}
      meta={<>{game.season} season / {game.gameType === 'PST' ? 'Playoffs' : 'Regular season'} / Puck drop {nhlPuckDropLabel(game.startUtc, true)} / {state.label}</>} />
    <NhlGameHero game={game} />
    <Tabs key={game.gameId} className="nfl-game-tabs" defaultActiveKey="props" destroyOnHidden aria-label="Game sections" animated={false}
      items={[
        { key: 'matchup', label: 'Matchup', children: <div className="nfl-game-main">
          <NhlGameMarket game={game} />
          <LineMovementChart detail={game} caveat="Before puck drop" spreadTitle="Puck line"
            emptyMessage="No pre-puck-drop puck-line or total history is stored for this game." />
        </div> },
        { key: 'props', label: 'Player Props', children: <NhlLineOnlyProps key={game.gameId} gameId={game.gameId} /> },
      ]} />
  </div></div>
}
