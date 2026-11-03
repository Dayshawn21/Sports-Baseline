import type { ReactNode } from 'react'
import PageHead from '~/components/shared/PageHead'
import '~/pages/nfl-slate.css'
import '~/pages/nfl-player.css'

interface ShellProps {
  /** The sport's own class (`nba-player`), beside the shared `nfl-slate nfl-player`; NFL adds none. */
  sportClass?: string
  crumb: ReactNode
  title: string
  meta?: ReactNode
  /** The season strip under the title. */
  stats?: ReactNode
  /** Page controls beside the title, e.g. the Next match link. */
  actions?: ReactNode
  /** The injury or availability line under the head. */
  notice?: ReactNode
  children: ReactNode
}

/** The frame every player page shares: container, Back crumb, head and status line. */
export function PlayerPageShell({ sportClass, crumb, title, meta, stats, actions, notice, children }: ShellProps) {
  return <div className={['page-shell nfl-slate nfl-player', sportClass].filter(Boolean).join(' ')}><div className="page-container is-wide">
    {crumb}
    <PageHead title={title} meta={meta} stats={stats} actions={actions} />
    {notice}
    {children}
  </div></div>
}

interface NotFoundProps {
  sportClass?: string
  crumb: ReactNode
  /** The sport's name in the message and the placeholder head, e.g. `NBA`. */
  sport: string
}

export function PlayerNotFound({ sportClass, crumb, sport }: NotFoundProps) {
  return <PlayerPageShell sportClass={sportClass} crumb={crumb} title={`${sport} player`}>
    <div className="nfl-player-empty is-page">Player not found. The link may be wrong, or the player is not in the loaded {sport} data.</div>
  </PlayerPageShell>
}
