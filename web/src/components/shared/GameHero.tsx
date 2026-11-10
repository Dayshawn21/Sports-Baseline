import type { ReactNode } from 'react'
import TeamLogo from '~/components/shared/TeamLogo'
import { usePhoneLayout } from '~/hooks/usePhoneLayout'
import { gameStartParts, type GameState } from '~/utils/gameState'
import type { LogoSport } from '~/utils/teamLogo'
import './game-page.css'

export interface GameHeroTeam {
  code: string
  /** Null when the sport's data carries no record, or while it loads; the line then stays empty rather than guessing. */
  record: string | null
  /** Null until the final is stored. */
  score: number | null
}

interface Props {
  sport: LogoSport
  away: GameHeroTeam
  home: GameHeroTeam
  state: GameState
  startUtc: string | null
  /** A small line under the middle, e.g. NFL venue and conditions. */
  detail?: ReactNode
}

function Team({ sport, team, side, phone }: { sport: LogoSport, team: GameHeroTeam, side: 'away' | 'home', phone: boolean }) {
  return <div className={`game-hero__team is-${side}`}>
    <TeamLogo sport={sport} code={team.code} size={phone ? 32 : 44} />
    <div className="game-hero__name"><strong>{team.code}</strong><small>{team.record}</small></div>
  </div>
}

function Middle({ away, home, state, startUtc }: Pick<Props, 'away' | 'home' | 'state' | 'startUtc'>) {
  const start = gameStartParts(startUtc)
  if (state.phase === 'final' && away.score !== null && home.score !== null) {
    return <>
      <span className="game-hero__score" aria-label={`${away.code} ${away.score}, ${home.code} ${home.score}`}>
        <span className={away.score < home.score ? 'is-loser' : undefined}>{away.score}</span>
        <span className={home.score < away.score ? 'is-loser' : undefined}>{home.score}</span>
      </span>
      <small>{state.label}</small>
    </>
  }
  if (state.phase === 'upcoming') {
    return start ? <><span className="game-hero__big">{start.clock}</span><small>{start.day}</small></> : <span className="game-hero__big">Time TBD</span>
  }
  const since = state.phase === 'live' || state.phase === 'pending' ? start && `Started ${start.clock}` : start?.day
  return <><span className="game-hero__big">{state.label}</span>{since && <small>{since}</small>}</>
}

/** The game page's head row, the same for every sport: away, the game's moment, home. Display only. */
export function GameHero({ sport, away, home, state, startUtc, detail }: Props) {
  const phone = usePhoneLayout()
  return <div className="game-hero" role="group" aria-label="Teams and game status">
    <Team sport={sport} team={away} side="away" phone={phone} />
    <div className="game-hero__mid">
      <Middle away={away} home={home} state={state} startUtc={startUtc} />
      {detail && <small className="game-hero__detail">{detail}</small>}
    </div>
    <Team sport={sport} team={home} side="home" phone={phone} />
  </div>
}
