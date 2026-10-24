import type { nhlContextSource, nhlGoalieLabel, nhlSlateContext } from '~/utils/nhlContext'

function Source({ report }: { report: ReturnType<typeof nhlContextSource> }) {
  return <p className="nhl-context-source">ESPN / {report.label} / {report.fetchedAt
    ? <>Fetched <time dateTime={report.fetchedAt}>{report.fetchedLabel}</time></>
    : report.fetchedLabel}</p>
}

function Goalie({ team, goalie }: { team: string, goalie: ReturnType<typeof nhlGoalieLabel> }) {
  return <p className="nhl-context-side"><strong>{team}</strong> <span>{goalie.name && <>{goalie.name} / </>}{goalie.status}
    {goalie.unresolved && <span className="nhl-context-unresolved"> / Unresolved identity</span>}</span></p>
}

export function NhlSlateContext({ context, away, home }: {
  context: ReturnType<typeof nhlSlateContext>, away: string, home: string,
}) {
  return <div className="nhl-slate-context">
    <section aria-label={`${away} at ${home} starting goalies`}>
      <h3>Starting goalies</h3>
      <Goalie team={away} goalie={context.goalies.away} /><Goalie team={home} goalie={context.goalies.home} />
      <Source report={context.goalies} />
    </section>
    <section aria-label={`${away} at ${home} injuries reported`}>
      <h3>Injuries reported</h3>
      <p>{away} {context.injuries.away ?? 'Unavailable'} / {home} {context.injuries.home ?? 'Unavailable'}</p>
      {context.injuries.empty && <p>No injuries reported by ESPN.</p>}
      <Source report={context.injuries} />
    </section>
  </div>
}
