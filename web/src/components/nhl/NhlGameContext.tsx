import type { NhlGameDetail } from '~/types/nhl'
import type { NhlGoalieSide, NhlInjury } from '~/types/nhlContext'
import { nhlContextSource, nhlContextTime, nhlGoalieLabel, nhlInjuryDetails, unavailableNhlContext } from '~/utils/nhlContext'

function Source({ report, sourceTimestamp }: { report: ReturnType<typeof nhlContextSource>, sourceTimestamp: string | null }) {
  const sourceTime = nhlContextTime(sourceTimestamp)
  return <div className="nhl-game-context-source">
    <p>ESPN / {report.label} / {report.fetchedAt
      ? <>Fetched <time dateTime={report.fetchedAt}>{report.fetchedLabel}</time></> : report.fetchedLabel}</p>
    <p>Source updated {sourceTime ? <time dateTime={sourceTime.dateTime}>{sourceTime.label}</time> : 'time unavailable'}</p>
  </div>
}

function Goalie({ team, side, available }: { team: string, side: NhlGoalieSide, available: boolean }) {
  const goalie = nhlGoalieLabel(side, available)
  return <div className="nhl-game-goalie">
    <h3>{team}</h3>
    {goalie.name && <p className="nhl-game-goalie-name">{goalie.name}</p>}
    <p>{goalie.status}</p>
    {goalie.unresolved && <p className="nhl-game-context-meta">Unresolved identity</p>}
  </div>
}

function Injuries({ team, entries, available }: { team: string, entries: NhlInjury[], available: boolean }) {
  return <section className="nhl-game-injury-team" aria-label={`${team} injuries`}>
    <h3>{team} <span>{available ? `${entries.length} reported` : 'Unavailable'}</span></h3>
    {!available ? <p>Injury report unavailable.</p> : entries.length === 0 ? <p>No injuries reported by ESPN.</p>
      : <ul>{entries.map(entry => {
        const injury = nhlInjuryDetails(entry)
        return <li key={injury.espnAthleteId}>
          <div className="nhl-game-injury-title"><strong>{injury.playerName}</strong><span>{injury.status}</span></div>
          {injury.detail && <p>{injury.detail}</p>}
          {injury.identity && <p className="nhl-game-context-meta">{injury.identity}</p>}
          <p className="nhl-game-context-meta">Source updated {injury.updated
            ? <time dateTime={injury.updated.dateTime}>{injury.updated.label}</time> : 'time unavailable'}</p>
          {injury.returnDate && <p className="nhl-game-context-meta">Return date reported by ESPN: {injury.returnDate}</p>}
        </li>
      })}</ul>}
  </section>
}

export function NhlGameContext({ game, now }: { game: NhlGameDetail, now: Date }) {
  const context = game.context ?? unavailableNhlContext(game.awayTeam, game.homeTeam)
  const goalies = nhlContextSource(context.goalies, game.startUtc, now)
  const injuries = nhlContextSource(context.injuries, game.startUtc, now)
  return <>
    <section className="nfl-game-card nhl-game-context" aria-label="Starting goalies">
      <div className="nfl-game-card__head"><h2 className="nfl-game-label">Starting goalies</h2></div>
      <p className="nfl-game-note">Expected and Confirmed describe ESPN's report. Late changes may be missing.</p>
      <div className="nhl-game-context-teams">
        <Goalie team={game.awayTeam} side={context.goalies.away} available={goalies.freshness !== 'unavailable'} />
        <Goalie team={game.homeTeam} side={context.goalies.home} available={goalies.freshness !== 'unavailable'} />
      </div>
      <Source report={goalies} sourceTimestamp={context.goalies.sourceTimestamp} />
    </section>
    <section className="nfl-game-card nhl-game-context" aria-label="Injuries reported">
      <div className="nfl-game-card__head"><h2 className="nfl-game-label">Injuries reported</h2></div>
      <p className="nfl-game-note">Source reports only. An absent name does not establish availability.</p>
      <Source report={injuries} sourceTimestamp={context.injuries.sourceTimestamp} />
      <div className="nhl-game-context-teams">
        <Injuries team={game.awayTeam} entries={context.injuries.away} available={injuries.freshness !== 'unavailable'} />
        <Injuries team={game.homeTeam} entries={context.injuries.home} available={injuries.freshness !== 'unavailable'} />
      </div>
    </section>
  </>
}
