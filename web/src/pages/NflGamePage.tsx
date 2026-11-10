import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { NflBestLineCard } from '~/components/nfl/NflBestLineCard'
import { NflDataGuide } from '~/components/nfl/NflDataGuide'
import { NflGameMarketBlock } from '~/components/nfl/NflGameMarket'
import { NflGameProps } from '~/components/nfl/NflGameProps'
import { NflGameContext } from '~/components/nfl/NflGameContext'
import { NflGameAvailability, NflGameSidebar } from '~/components/nfl/NflGameSidebar'
import { NflLineMovementChart } from '~/components/nfl/NflLineMovementChart'
import { NflTeamStatsMatchup } from '~/components/nfl/NflTeamStatsMatchup'
import ErrorState from '~/components/shared/ErrorState'
import { GameHero } from '~/components/shared/GameHero'
import { GameNotFound, GamePageShell, GamePageState } from '~/components/shared/GamePageShell'
import LoadingState from '~/components/shared/LoadingState'
import { useNflGame, useNflGameNotes, useNflSlate } from '~/hooks/useNfl'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { useRegisterSlateCommand } from '~/components/shared/SlateCommandProvider'
import type { NflSlateGame, NflTeamContext } from '~/types/nfl'
import { gameStartLabel, gameState } from '~/utils/gameState'
import { isNotFound } from '~/utils/httpError'
import { conditionsLabel, parseGameId, recordLabel } from '~/utils/nflGame'
import { kickoffWindows } from '~/utils/nflSlate'
import { nflSlateCommandRows } from '~/utils/slateCommand'
import './nfl-slate.css'
import './nfl-prop-board.css'
import './nfl-game.css'

const VENUE_LABELS: Record<string, string> = { dome: 'Dome', outdoor: 'Outdoor', retractable: 'Retractable roof' }

function venueLine(game: NflSlateGame | null): string | null {
  return game ? `${VENUE_LABELS[game.weather.venueType] ?? game.weather.venueType} · ${conditionsLabel(game.weather)}` : null
}

/** `context` is undefined while the slate loads, so no record is claimed before it arrives. */
function heroRecord(context: NflTeamContext | null | undefined): string | null {
  return context === undefined ? null : recordLabel(context)
}

export default function NflGamePage() {
  const gameId = parseGameId(useParams().gameId)
  const detail = useNflGame(gameId)
  const slate = useNflSlate(detail.data?.season ?? null, detail.data?.week ?? null)
  const notes = useNflGameNotes(detail.data?.season ?? null, detail.data?.week ?? null)
  useRegisterDetailTitle(detail.isSuccess && gameId !== null ? `${detail.data.awayTeam} @ ${detail.data.homeTeam}` : null)
  // The week's slate is already loaded for the market, so search can jump to any other game from here.
  const commandScope = useMemo(() => detail.data && slate.data
    ? { periodKey: `${detail.data.season}-${detail.data.week}`, rows: nflSlateCommandRows(kickoffWindows(slate.data.games).flatMap(window => window.games)) }
    : null, [detail.data, slate.data])
  useRegisterSlateCommand(commandScope)
  if (gameId === null || isNotFound(detail.error)) return <GameNotFound sport="nfl" reason="It may not be a loaded regular-season game, or the link is wrong." />
  if (detail.isLoading) return <GamePageState sport="nfl"><LoadingState message="Loading game..." /></GamePageState>
  if (detail.isError || !detail.data) return <GamePageState sport="nfl"><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></GamePageState>
  const data = detail.data
  const game = slate.data?.games.find(item => item.gameId === gameId) ?? null
  const gameNotes = notes.data?.games.find(item => item.gameId === gameId)
  const state = gameState(data.status, data.startUtc, new Date())
  return <GamePageShell sport="nfl" title={`${data.awayTeam} @ ${data.homeTeam}`} tabsKey={gameId}
    meta={[`${data.season} season`, `Week ${data.week}`, gameStartLabel(data.startUtc), state.label]}
    hero={<GameHero sport="nfl" state={state} startUtc={data.startUtc} detail={venueLine(game)}
      away={{ code: data.awayTeam, record: heroRecord(game?.awayContext), score: gameNotes?.awayScore ?? null }}
      home={{ code: data.homeTeam, record: heroRecord(game?.homeContext), score: gameNotes?.homeScore ?? null }} />}
    notice={<NflDataGuide />}
    matchup={<div className="nfl-game-layout">
      <div className="nfl-game-main">
        {slate.isLoading && <LoadingState message="Loading market..." />}
        {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
        {game && <NflGameMarketBlock game={game} notes={gameNotes} />}
        {state.phase === 'upcoming' && gameNotes && <NflBestLineCard bestLine={gameNotes.bestLine} homeTeam={data.homeTeam} awayTeam={data.awayTeam} />}
        <NflLineMovementChart detail={data} />
        {gameNotes && <NflTeamStatsMatchup notes={gameNotes} />}
        <NflGameContext game={data} notesContext={gameNotes?.matchupContext} section="matchup" />
        <NflGameAvailability notes={gameNotes} isLoading={notes.isLoading} isError={notes.isError} />
      </div>
      <NflGameSidebar notes={gameNotes} isLoading={notes.isLoading} isError={notes.isError} />
    </div>}
    props={<div className="nfl-game-main">
      {slate.isLoading && <LoadingState message="Loading player props..." />}
      {slate.isError && <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />}
      {game && slate.data && <NflGameProps games={slate.data.games} game={game} week={{ season: data.season, week: data.week }} />}
      {slate.isSuccess && !game && <p className="nfl-game-empty">No player props stored for this game.</p>}
      <NflGameContext game={data} section="usage" />
    </div>} />
}
