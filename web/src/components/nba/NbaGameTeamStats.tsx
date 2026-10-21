import type { NbaGameDetail, NbaTeamSeasonStats, NbaTeamStatRate } from '~/types/nba'
import { NBA_TEAM_STATS, nbaTeamRateText } from '~/utils/nbaTeamStats'
import './nba-game-team-stats.css'

function Rate({ rate, completed }: { rate: NbaTeamStatRate, completed: number }) {
  const text = nbaTeamRateText(rate, completed)
  return <td>
    <strong aria-label={rate.perGame === null ? 'Unavailable' : undefined}>{text.value}</strong>
    <span>{text.rank}</span>
    <span>{text.sample}</span>
    {text.notes.map(note => <span className="nba-team-stats__note" key={note}>{note}</span>)}
  </td>
}

function Team({ team, name }: { team: NbaTeamSeasonStats, name: string }) {
  return <article>
    <h4>{name} <small>{team.team}</small></h4>
    {team.completedGames === 0 && <p className="nba-team-stats__empty">No earlier regular-season games this season.</p>}
    <table>
      <caption className="sr-only">{name} season-to-date team stats per game</caption>
      <thead><tr><th scope="col">Per game</th><th scope="col">For</th><th scope="col">Allowed</th></tr></thead>
      <tbody>{NBA_TEAM_STATS.map(({ key, label }) => <tr key={key}>
        <th scope="row">{label}</th>
        <Rate rate={team.stats[key].for} completed={team.completedGames} />
        <Rate rate={team.stats[key].allowed} completed={team.completedGames} />
      </tr>)}</tbody>
    </table>
  </article>
}

export function NbaGameTeamStats({ detail }: { detail: NbaGameDetail }) {
  const context = detail.teamStats
  return <section className="nfl-line-only nba-team-stats" aria-label="Team stats">
    <h3 className="nfl-game-label">Team stats <small>regular season, display context only</small></h3>
    <div className="prop-table-panel">
      {!context ? <p className="nba-team-stats__empty">Team stats unavailable.</p> : <>
        <p className="nba-team-stats__context">
          {context.season}-{String(context.season + 1).slice(-2)} season. Games before <time dateTime={context.beforeDate}>{context.beforeDate}</time> (Eastern date).
          {' '}Rank 1 means highest for, fewest allowed.
        </p>
        <div className="nba-team-stats__teams">
          <Team team={context.away} name={detail.awayTeamName} />
          <Team team={context.home} name={detail.homeTeamName} />
        </div>
        <p className="nba-team-stats__basis">Stored player box-score totals, including overtime. Rebounds exclude team-only rebounds. Team totals are not a player projection.</p>
      </>}
    </div>
  </section>
}
