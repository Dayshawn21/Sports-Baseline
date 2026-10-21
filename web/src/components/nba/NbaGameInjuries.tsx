import type { NbaGameDetail } from '~/types/nba'
import { NbaInjuryTag } from '~/components/nba/NbaInjury'
import { nbaInjuryFreshness, nbaInjuryTime } from '~/utils/nbaInjuries'
import './nba-game-injuries.css'

export function NbaGameInjuries({ detail }: { detail: NbaGameDetail }) {
  const report = detail.injuryReport
  const now = new Date()
  const freshness = nbaInjuryFreshness(report, detail.startUtc, now)
  const preTip = detail.startUtc !== null && Date.parse(detail.startUtc) <= now.getTime()
  return <section className="nfl-line-only nba-game-injuries" aria-label="Team injury reports">
    <h3 className="nfl-game-label">Injuries <small>ESPN reports, display context only</small></h3>
    <div className="prop-table-panel">
      {freshness !== 'unavailable' && <p className="nba-game-injuries__source">
        {freshness === 'stale' ? 'Stale report. ' : ''}{preTip ? 'ESPN pre-tip snapshot: ' : 'ESPN snapshot: '}
        <time dateTime={report.fetchedAt ?? undefined}>{nbaInjuryTime(report.fetchedAt)}</time>
      </p>}
      <div className="nba-game-injuries__teams">
        {[[detail.awayTeam, detail.awayTeamName], [detail.homeTeam, detail.homeTeamName]].map(([team, name]) => {
          const injuries = report?.injuries.filter(entry => entry.team === team) ?? []
          return <article key={team} aria-label={`${name} injuries`}>
            <h4>{name}</h4>
            {freshness === 'unavailable' ? <p>Injury report unavailable.</p>
              : injuries.length === 0 ? <p>No injuries reported by ESPN.</p>
                : <ul>{injuries.map(entry => <li key={entry.espnAthleteId}>
                  <div className="nba-game-injuries__player"><strong>{entry.playerName}</strong><NbaInjuryTag injury={entry} freshness={freshness} /></div>
                  <p>{entry.detail ?? 'No injury detail provided by ESPN.'}</p>
                  {entry.athleteTeam && entry.athleteTeam !== entry.team && <p>ESPN lists this athlete with {entry.athleteTeam}; this report is filed under {entry.team}.</p>}
                  {entry.returnDate && <p>Expected return (ESPN): {entry.returnDate}</p>}
                  {entry.sourceUpdatedAt && <p className="nba-game-injuries__updated">ESPN entry updated: <time dateTime={entry.sourceUpdatedAt}>{nbaInjuryTime(entry.sourceUpdatedAt)}</time></p>}
                </li>)}</ul>}
          </article>
        })}
      </div>
    </div>
  </section>
}
