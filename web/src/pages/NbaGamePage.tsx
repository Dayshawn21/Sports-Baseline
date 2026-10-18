import { useMemo, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { NbaGameHero, NbaGameMarket } from '~/components/nba/NbaGameHero'
import { NbaLineOnlyProps } from '~/components/nba/NbaLineOnlyProps'
import { NbaProps } from '~/components/nba/NbaProps'
import { NflLineMovementChart } from '~/components/nfl/NflLineMovementChart'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import { useNbaGame } from '~/hooks/useNba'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { isNotFound } from '~/utils/httpError'
import { parseGameId } from '~/utils/nbaGame'
import { nbaSlateCard } from '~/utils/nbaSlate'
import { kickoffLabel } from '~/utils/nflGame'
import type { NbaGameDetail } from '~/types/nba'
import './nfl-slate.css'
import './nfl-game.css'
import './nba-game.css'

const GAME_TYPE_LABELS: Record<NbaGameDetail['gameType'], string> = { REG: 'Regular season', PIN: 'Play-in', PST: 'Playoffs' }

function BackLink({ gameDate }: { gameDate: string | null }) {
  return <Link className="nfl-game-crumb" to={gameDate === null ? '/nba' : `/nba?date=${gameDate}`}>← NBA slate</Link>
}

function GamePageState({ children }: { children: ReactNode }) {
  return <div className="page-shell nfl-slate nfl-game nba-game"><div className="page-container is-wide">
    <BackLink gameDate={null} />
    <PageHead title="NBA game" />
    {children}
  </div></div>
}

function NotFound() {
  return <GamePageState><div className="nfl-game-empty is-page">Game not found. It may be a preseason game, or the link is wrong.</div></GamePageState>
}

export default function NbaGamePage() {
  const gameId = parseGameId(useParams().gameId)
  const detail = useNbaGame(gameId)
  const card = useMemo(() => detail.data ? nbaSlateCard(detail.data, new Date()) : null, [detail.data])
  useRegisterDetailTitle(detail.isSuccess && gameId !== null ? `${detail.data.awayTeam} @ ${detail.data.homeTeam}` : null)
  if (gameId === null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <GamePageState><LoadingState message="Loading game..." /></GamePageState>
  if (detail.isError || !detail.data || !card) return <GamePageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></GamePageState>
  return <div className="page-shell nfl-slate nfl-game nba-game"><div className="page-container is-wide">
    <BackLink gameDate={detail.data.gameDate} />
    <PageHead title={`${detail.data.awayTeam} @ ${detail.data.homeTeam}`}
      meta={<>{detail.data.season} season · {GAME_TYPE_LABELS[detail.data.gameType]} · {kickoffLabel(detail.data.startUtc)} · {card.stateLabel ?? 'Scheduled'}</>} />
    <NbaGameHero card={card} />
    <div className="nfl-game-layout">
      <main className="nfl-game-main">
        <NbaGameMarket detail={detail.data} card={card} />
        <NflLineMovementChart detail={detail.data} caveat="Before tip-off" />
        <NbaProps gameId={detail.data.gameId} />
        <NbaLineOnlyProps gameId={detail.data.gameId} />
      </main>
    </div>
  </div></div>
}
