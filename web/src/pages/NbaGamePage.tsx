import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { NbaGameMarket } from '~/components/nba/NbaGameMarket'
import { NbaGameInjuries } from '~/components/nba/NbaGameInjuries'
import { NbaGameTeamStats } from '~/components/nba/NbaGameTeamStats'
import { NbaLineOnlyProps } from '~/components/nba/NbaLineOnlyProps'
import { NbaProps } from '~/components/nba/NbaProps'
import { NflLineMovementChart } from '~/components/nfl/NflLineMovementChart'
import ErrorState from '~/components/shared/ErrorState'
import { GameHero } from '~/components/shared/GameHero'
import { GameNotFound, GamePageShell, GamePageState } from '~/components/shared/GamePageShell'
import LoadingState from '~/components/shared/LoadingState'
import { useNbaGame, useNbaSlate, useNbaSlateGaps } from '~/hooks/useNba'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { useRegisterSlateCommand } from '~/components/shared/SlateCommandProvider'
import { gameStartLabel, gameState } from '~/utils/gameState'
import { isNotFound } from '~/utils/httpError'
import { parseGameId } from '~/utils/nbaGame'
import { nbaSlateCard } from '~/utils/nbaSlate'
import { nbaSlateCommandRows } from '~/utils/slateCommand'
import type { NbaGameDetail } from '~/types/nba'
import './nba-game.css'

const GAME_TYPE_LABELS: Record<NbaGameDetail['gameType'], string> = { REG: 'Regular season', PIN: 'Play-in', PST: 'Playoffs' }

export default function NbaGamePage() {
  const gameId = parseGameId(useParams().gameId)
  const detail = useNbaGame(gameId)
  const card = useMemo(() => detail.data ? nbaSlateCard(detail.data, new Date()) : null, [detail.data])
  useRegisterDetailTitle(detail.isSuccess && gameId !== null ? `${detail.data.awayTeam} @ ${detail.data.homeTeam}` : null)
  // The game's own date's slate, so search can jump to any other game that night, as the NFL game page does for its week.
  const slate = useNbaSlate(detail.data?.gameDate ?? null, detail.isSuccess)
  const gaps = useNbaSlateGaps(slate.data?.date ?? null)
  const commandScope = useMemo(() => slate.data
    ? { periodKey: slate.data.date, rows: nbaSlateCommandRows(slate.data.games, gaps.isError ? [] : gaps.data?.items ?? []) }
    : null, [gaps.data, gaps.isError, slate.data])
  useRegisterSlateCommand(commandScope)
  if (gameId === null || isNotFound(detail.error)) return <GameNotFound sport="nba" reason="It may be a preseason game, or the link is wrong." />
  if (detail.isLoading) return <GamePageState sport="nba"><LoadingState message="Loading game..." /></GamePageState>
  if (detail.isError || !detail.data || !card) return <GamePageState sport="nba"><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></GamePageState>
  const data = detail.data
  const state = gameState(data.status, data.startUtc, new Date())
  return <GamePageShell sport="nba" to={`/nba?date=${data.gameDate}`} title={`${data.awayTeam} @ ${data.homeTeam}`} tabsKey={gameId}
    meta={[`${data.season} season`, GAME_TYPE_LABELS[data.gameType], gameStartLabel(data.startUtc), state.label]}
    hero={<GameHero sport="nba" state={state} startUtc={data.startUtc}
      away={{ code: data.awayTeam, record: card.away.record, score: card.away.score }}
      home={{ code: data.homeTeam, record: card.home.record, score: card.home.score }} />}
    matchup={<div className="nfl-game-layout">
      <div className="nfl-game-main">
        <NbaGameMarket detail={data} card={card} />
        <NflLineMovementChart detail={data} caveat="Before tip-off" />
        <NbaGameInjuries detail={data} />
        <NbaGameTeamStats detail={data} />
      </div>
    </div>}
    props={<div className="nfl-game-main">
      <NbaProps key={`props:${data.gameId}`} game={data} gameDate={data.gameDate} />
      <NbaLineOnlyProps key={`other:${data.gameId}`} gameId={data.gameId} startUtc={data.startUtc} gameDate={data.gameDate} />
    </div>} />
}
