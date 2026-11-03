import type { NhlPlayerProps } from '~/types/nhl'
import type { NhlGoalieContext, NhlGoalieSide } from '~/types/nhlContext'
import { nhlContextSource, nhlContextTime, nhlGoalieLabel, nhlInjuryDetails } from '~/utils/nhlContext'
import { nhlPlayerInjuryReport } from '~/utils/nhlPlayer'

type Report = ReturnType<typeof nhlContextSource>

function Source({ report, sourceTimestamp }: { report: Report, sourceTimestamp: string | null }) {
  const sourceTime = nhlContextTime(sourceTimestamp)
  return <div className="nhl-game-context-source">
    <p>ESPN / {report.label} / {report.fetchedAt
      ? <>Fetched <time dateTime={report.fetchedAt}>{report.fetchedLabel}</time></> : report.fetchedLabel}</p>
    <p>Source updated {sourceTime ? <time dateTime={sourceTime.dateTime}>{sourceTime.label}</time> : 'time unavailable'}</p>
  </div>
}

function Injury({ player, now }: { player: NhlPlayerProps, now: Date }) {
  const report = nhlContextSource(nhlPlayerInjuryReport(player.injury), player.game?.startUtc ?? null, now)
  const entry = player.injury.entry === null ? null : nhlInjuryDetails(player.injury.entry)
  return <section className="nhl-player-evidence__section" aria-label="Injury report">
    <h4>Injury report</h4>
    {report.freshness === 'unavailable' ? <p>Injury report unavailable.</p> : <>
      {entry ? <>
        <p><strong>{entry.status}</strong></p>
        {entry.detail && <p>{entry.detail}</p>}
        {entry.identity && <p className="nhl-game-context-meta">{entry.identity}</p>}
        {entry.returnDate && <p className="nhl-game-context-meta">Return date reported by ESPN: {entry.returnDate}</p>}
        {entry.updated && <p className="nhl-game-context-meta">Entry updated <time dateTime={entry.updated.dateTime}>{entry.updated.label}</time></p>}
      </> : <p>No injury listed by ESPN for this player. This is a source report, not proof the player is available.</p>}
      <Source report={report} sourceTimestamp={player.injury.sourceTimestamp} />
    </>}
  </section>
}

function Goalie({ side, available }: { side: NhlGoalieSide, available: boolean }) {
  const goalie = nhlGoalieLabel(side, available)
  return <div className="nhl-game-goalie">
    <h3>{side.team}</h3>
    {goalie.name && <p className="nhl-game-goalie-name">{goalie.name}</p>}
    <p>{goalie.status}</p>
    {goalie.unresolved && <p className="nhl-game-context-meta">Unresolved identity</p>}
  </div>
}

/** The two teams' goalie reports, the player's own team first. */
function goalieSides(goalies: NhlGoalieContext, team: string | null): NhlGoalieSide[] {
  return goalies.away.team === team ? [goalies.away, goalies.home] : [goalies.home, goalies.away]
}

function Goalies({ player, now }: { player: NhlPlayerProps, now: Date }) {
  const goalies = player.goalies
  const report = nhlContextSource(goalies ?? undefined, player.game?.startUtc ?? null, now)
  const available = report.freshness !== 'unavailable'
  return <section className="nhl-player-evidence__section" aria-label="Starting goalies">
    <h4>Starting goalies</h4>
    {goalies === null || !available ? <p>Starting goalie report unavailable.</p> : <>
      <p className="nhl-game-context-meta">Expected and Confirmed describe ESPN's report. Late changes may be missing.</p>
      <div className="nhl-game-context-teams">
        {goalieSides(goalies, player.team).map(side => <Goalie key={side.team} side={side} available={available} />)}
      </div>
      <Source report={report} sourceTimestamp={goalies.sourceTimestamp} />
    </>}
  </section>
}

/** The injury report and starting goalies for the player's game: source reports shown as reported, not a verdict on availability. */
export function NhlPlayerEvidence({ player, now }: { player: NhlPlayerProps, now: Date }) {
  return <div className="nhl-game-context nhl-player-evidence">
    <Injury player={player} now={now} />
    <Goalies player={player} now={now} />
  </div>
}
