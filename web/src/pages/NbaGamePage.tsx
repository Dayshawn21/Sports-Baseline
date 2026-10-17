import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { NbaGameHero, NbaGameMarket } from '~/components/nba/NbaGameHero'
import { NbaLineOnlyProps } from '~/components/nba/NbaLineOnlyProps'
import { NbaProps } from '~/components/nba/NbaProps'
import { NflLineMovementChart } from '~/components/nfl/NflLineMovementChart'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNbaGame } from '~/hooks/useNba'
import { isNotFound } from '~/utils/httpError'
import { parseGameId } from '~/utils/nbaGame'
import { nbaSlateCard } from '~/utils/nbaSlate'
import './nfl-slate.css'
import './nfl-game.css'
import './nba-game.css'

function BackLink({ gameDate }: { gameDate: string | null }) {
  return <Link className="nfl-game-crumb" to={gameDate === null ? '/nba' : `/nba?date=${gameDate}`}>← NBA slate</Link>
}

function NotFound() {
  return <div className="page-shell nfl-slate nfl-game nba-game"><div className="page-container is-wide">
    <BackLink gameDate={null} />
    <div className="nfl-game-empty is-page">Game not found. It may be a preseason game, or the link is wrong.</div>
  </div></div>
}

export default function NbaGamePage() {
  const gameId = parseGameId(useParams().gameId)
  const detail = useNbaGame(gameId)
  const card = useMemo(() => detail.data ? nbaSlateCard(detail.data, new Date()) : null, [detail.data])
  if (gameId === null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <LoadingState message="Loading game..." />
  if (detail.isError || !detail.data || !card) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
  return <div className="page-shell nfl-slate nfl-game nba-game"><div className="page-container is-wide">
    <BackLink gameDate={detail.data.gameDate} />
    <NbaGameHero detail={detail.data} card={card} />
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
