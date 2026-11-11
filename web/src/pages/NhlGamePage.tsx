import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { NhlGameMarket } from '~/components/nhl/NhlGameMarket'
import { NhlGameContext } from '~/components/nhl/NhlGameContext'
import { NhlGameProps } from '~/components/nhl/NhlGameProps'
import { NflLineMovementChart as LineMovementChart } from '~/components/nfl/NflLineMovementChart'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import ErrorState from '~/components/shared/ErrorState'
import { GameHero } from '~/components/shared/GameHero'
import { GameNotFound, GamePageShell, GamePageState } from '~/components/shared/GamePageShell'
import LoadingState from '~/components/shared/LoadingState'
import { useRegisterSlateCommand } from '~/components/shared/SlateCommandProvider'
import { useNhlGame, useNhlSlate } from '~/hooks/useNhl'
import { gameStartLabel, gameState, withEndPeriod } from '~/utils/gameState'
import { isNotFound } from '~/utils/httpError'
import { parseNhlGameId } from '~/utils/nhlGame'
import { nhlSlateCommandRows } from '~/utils/slateCommand'
import './nhl-game.css'

export default function NhlGamePage() {
  const gameId = parseNhlGameId(useParams().gameId)
  const detail = useNhlGame(gameId)
  useRegisterDetailTitle(detail.isSuccess && gameId !== null ? `${detail.data.awayTeam} @ ${detail.data.homeTeam}` : null)
  // The game's own date's slate, so search can jump to any other game that night, as the NFL game page does for its week.
  const slate = useNhlSlate(detail.data?.gameDate ?? null, detail.isSuccess)
  const commandScope = useMemo(() => slate.data ? { periodKey: slate.data.date, rows: nhlSlateCommandRows(slate.data.games) } : null, [slate.data])
  useRegisterSlateCommand(commandScope)
  if (gameId === null || isNotFound(detail.error)) return <GameNotFound sport="nhl" reason="Check the link or return to the NHL slate." />
  if (detail.isLoading) return <GamePageState sport="nhl"><LoadingState message="Loading game..." /></GamePageState>
  if (detail.isError || !detail.data) return <GamePageState sport="nhl"><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></GamePageState>
  const game = detail.data
  const now = new Date()
  const state = withEndPeriod(gameState(game.status, game.startUtc, now), game.endPeriod)
  const final = state.phase === 'final'
  // The NHL API sends no team record yet, so the record line stays empty.
  return <GamePageShell sport="nhl" to={`/nhl?date=${game.gameDate}`} title={`${game.awayTeam} @ ${game.homeTeam}`} tabsKey={game.gameId}
    meta={[`${game.season} season`, game.gameType === 'PST' ? 'Playoffs' : 'Regular season', gameStartLabel(game.startUtc), state.label]}
    hero={<GameHero sport="nhl" state={state} startUtc={game.startUtc}
      away={{ code: game.awayTeam, record: null, score: final ? game.awayScore : null }}
      home={{ code: game.homeTeam, record: null, score: final ? game.homeScore : null }} />}
    matchup={<div className="nfl-game-main">
      <NhlGameMarket game={game} />
      <LineMovementChart detail={game} caveat="Before puck drop" spreadTitle="Puck line"
        emptyMessage="No pre-puck-drop puck-line or total history is stored for this game." />
      <NhlGameContext game={game} now={now} />
    </div>}
    props={<NhlGameProps key={game.gameId} game={game} />} />
}
