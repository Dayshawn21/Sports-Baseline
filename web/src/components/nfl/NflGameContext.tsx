import { Link } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNflGameContext } from '~/hooks/useNfl'
import type { NflGameDetail, NflMatchupContext } from '~/types/nfl'
import { orderedContextPlayers } from '~/utils/nflMatchupContext'
import { NflContextMetric } from './NflContextMetric'
import { NflPositionAllowedMatchup } from './NflTeamStatsMatchup'
import './nfl-matchup-context.css'

export function NflGameContext({ game, notesContext, section }: { game: NflGameDetail, notesContext?: NflMatchupContext | null, section?: 'matchup' | 'usage' }) {
  const context = useNflGameContext(game.gameId)
  const data = context.data?.gameId === game.gameId ? context.data : undefined
  const matchup = data?.matchupContext ?? notesContext
  const season = data?.season ?? game.season
  const cutoffWeek = data?.cutoffWeek ?? game.week - 1
  return <div className="nfl-context" aria-label={section === 'matchup' ? 'Matchup context' : section === 'usage' ? 'Usage context' : 'Matchup and usage context'}>
    {section !== 'usage' && matchup && <NflPositionAllowedMatchup context={matchup} season={season} cutoffWeek={cutoffWeek} />}
    {section === 'matchup' && context.isLoading && !matchup && <LoadingState message="Loading matchup context..." />}
    {section === 'matchup' && context.isError && <ErrorState error={context.error} onRetry={() => void context.refetch()} />}
    {section !== 'matchup' && <section className="nfl-game-card" aria-label="Player usage">
      <div className="nfl-game-card__head"><h2 className="nfl-game-label">Player usage</h2>
        <span className="nfl-game-side__meta">{season} season through Week {cutoffWeek}</span>
      </div>
      {context.isLoading && <div role="status"><LoadingState message="Loading matchup and usage context..." /></div>}
      {context.isError && <ErrorState error={context.error} onRetry={() => void context.refetch()} />}
      {data && (data.players.length === 0
        ? <p className="nfl-game-note">No unambiguous QB, RB, WR or TE roster memberships are stored for Week {data.week}.</p>
        : <details className="nfl-context-usage">
          <summary>Season usage shares <span>{data.players.length} {data.players.length === 1 ? 'player' : 'players'} on the Week {data.week} roster</span></summary>
          <p className="nfl-game-note">Target share uses all teammates' recorded targets; carry share uses all teammates' recorded carries, including QBs. Only covered player-games contribute. Game dates are UTC.</p>
          <table className="nfl-context-table nfl-context-usage__table">
            <caption className="sr-only">Season player usage shares through Week {cutoffWeek}; observed / eligible played games and covered dates per metric</caption>
            <colgroup><col className="nfl-context-table__label" /><col /><col /></colgroup>
            <thead><tr><th scope="col">Player</th><th scope="col">Target share</th><th scope="col">Carry share</th></tr></thead>
            <tbody>{orderedContextPlayers(data.players).map(player => <tr key={player.playerId}>
              <th scope="row"><Link to={`/nfl/player/${player.playerId}`}>{player.name}</Link>
                <small>{player.team} · {player.position}</small>
                {player.seasonUsage.teams.length > 1 && <small>History: {player.seasonUsage.teams.join(', ')}</small>}
              </th>
              <td>{player.position === 'QB' ? <span className="nfl-context-na">Not applicable</span> : <NflContextMetric metric={player.seasonUsage.targetShare} share />}</td>
              <td><NflContextMetric metric={player.seasonUsage.carryShare} share /></td>
            </tr>)}</tbody>
          </table>
        </details>)}
    </section>}
  </div>
}
