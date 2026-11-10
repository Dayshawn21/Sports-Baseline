import TeamLogo from '~/components/shared/TeamLogo'
import type { LogoSport } from '~/utils/teamLogo'
import './team-logo.css'

export interface MatchupTeam { code: string, score: number | null, lost?: boolean }

const LOGO_SIZE = 16

function Side({ sport, team, scored }: { sport: LogoSport, team: MatchupTeam, scored: boolean }) {
  return <span className={team.lost ? 'is-loser' : undefined}>
    <span className="slate-matchup__logo"><TeamLogo sport={sport} code={team.code} size={LOGO_SIZE} fallback="none" /></span>
    {scored ? `${team.code} ${team.score}` : team.code}
  </span>
}

/** "JAX @ BAL" with a logo before each code, plus the scores once both are in (the same rule as `slateMatchup`). */
export function SlateMatchupTeams({ sport, away, home }: { sport: LogoSport, away: MatchupTeam, home: MatchupTeam }) {
  const scored = away.score !== null && home.score !== null
  return <><Side sport={sport} team={away} scored={scored} /> @ <Side sport={sport} team={home} scored={scored} /></>
}
