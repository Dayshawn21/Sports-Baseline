import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { NflPlayerDetail, NflPlayerGame } from '~/types/nfl'
import { FOCUS_LABELS, isNflSpecialist, SPECIALIST_COLUMNS } from '~/utils/nflPlayer'

const MISSING = '--'

function result(game: NflPlayerGame): string {
  if (game.teamScore === null || game.opponentScore === null) return MISSING
  const outcome = game.teamScore > game.opponentScore ? 'W' : game.teamScore < game.opponentScore ? 'L' : 'T'
  return `${outcome} ${game.teamScore}-${game.opponentScore}`
}

function focusLine(game: NflPlayerGame): string {
  if (game.focusLine === null) return 'no stored line'
  return game.focusOutcome === null ? game.focusLine.toFixed(1) : `${game.focusLine.toFixed(1)} · ${game.focusOutcome}`
}

function optional(value: number | null, format: (value: number) => string = String): string {
  return value === null ? MISSING : format(value)
}

/** This season's games and the latest of last season, newest first, with the stored focus line per game. */
export function NflPlayerGameLog({ player }: { player: NflPlayerDetail }) {
  const [params] = useSearchParams()
  const selectedMarket = params.get('market')
  const specialist = isNflSpecialist(player.position)
  const columns = player.position === 'K' ? SPECIALIST_COLUMNS.K : player.position === 'P' ? SPECIALIST_COLUMNS.P : []
  const log = useRef<HTMLElement>(null)
  const selectedColumn = columns.find(column => column.market !== null && column.market === selectedMarket)?.field
  useEffect(() => {
    if (selectedColumn && player.gameLog.length > 0) log.current?.scrollIntoView({ block: 'start' })
  }, [selectedColumn, player.playerId, player.gameLog.length])
  const showPassing = player.position === 'QB' || player.gameLog.some(game => game.passingAttempts > 0)
  const lineLabel = player.focusMarket ? FOCUS_LABELS[player.focusMarket]?.line ?? null : null
  return <>
    <h2 className="nfl-player-section-title">Game log <small>{player.season} and the last 5 of {player.season - 1}</small></h2>
    <section ref={log} id="game-log" className="nfl-player-card" aria-label="Game log">
      {player.gameLog.length === 0
        ? <p className="nfl-player-card__empty">No completed games loaded for this player.</p>
        : <div className="nfl-player-table-wrap"><table className="nfl-player-table">
          <thead><tr>
            <th>Week</th><th>Opp</th><th>Result</th>
            {columns.map(column => <th key={column.field} className={column.market !== null && column.market === selectedMarket ? 'is-selected-market' : undefined}>{column.label}</th>)}
            {!specialist && <><th>Snaps</th>
            {showPassing && <><th>Cmp/Att</th><th>Pass yds</th></>}
            <th>Car</th><th>Rush yds</th><th>Tgt</th><th>Rec</th><th>Rec yds</th>
            <th title="Rushing plus receiving touchdowns; passing touchdowns are not counted">{showPassing ? 'Rush/rec TD' : 'TD'}</th>
            <th>PP fantasy</th></>}
            {lineLabel && <th>{lineLabel}</th>}
          </tr></thead>
          <tbody>{player.gameLog.map(game => <tr key={game.gameId}>
            <td className="is-text">{game.season} W{game.week}</td>
            <td>{game.isHome ? game.opponent : `@${game.opponent}`}</td>
            <td className="is-text">{result(game)}</td>
            {columns.map(column => <td key={column.field}>{optional(game[column.field])}</td>)}
            {!specialist && <><td>{optional(game.snapPct, value => `${Math.round(value * 100)}%`)}</td>
            {showPassing && <><td>{game.passingCompletions}/{game.passingAttempts}</td><td>{game.passingYards}</td></>}
            <td>{game.rushingAttempts}</td><td>{game.rushingYards}</td><td>{optional(game.targets)}</td>
            <td>{game.receptions}</td><td>{game.receivingYards}</td><td>{game.touchdowns}</td>
            <td>{optional(game.prizepicksFantasyPoints, value => value.toFixed(1))}</td></>}
            {lineLabel && <td className="is-dim">{focusLine(game)}</td>}
          </tr>)}</tbody>
        </table></div>}
    </section>
  </>
}
