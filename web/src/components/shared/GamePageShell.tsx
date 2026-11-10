import { Tabs } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import PageHead from '~/components/shared/PageHead'
import '~/pages/nfl-slate.css'
import '~/pages/nfl-game.css'
import './game-page.css'

export type GameSport = 'nfl' | 'nba' | 'nhl'

interface CrumbProps {
  sport: GameSport
  /** The slate the game sits on, e.g. `/nba?date=2026-11-09`; the sport's slate root by default. */
  to?: string
}

function GameCrumb({ sport, to }: CrumbProps) {
  return <Link className="game-crumb" to={to ?? `/${sport}`}>← {sport.toUpperCase()} slate</Link>
}

function shellClass(sport: GameSport): string {
  return ['page-shell nfl-slate nfl-game', sport === 'nfl' ? null : `${sport}-game`].filter(Boolean).join(' ')
}

interface ShellProps extends CrumbProps {
  /** `BUF @ KC`; the hero shows it, so the heading is for screen readers and the tab title. */
  title: string
  hero: ReactNode
  /** Joined with one separator, the same on every sport. */
  meta: string[]
  /** A line between the head and the tabs, e.g. NFL's data guide. */
  notice?: ReactNode
  tabsKey: number
  matchup: ReactNode
  props: ReactNode
}

/** The frame every game page shares: Back crumb, hero head with one meta line, then Player Props and Matchup tabs. */
export function GamePageShell({ sport, to, title, hero, meta, notice, tabsKey, matchup, props }: ShellProps) {
  return <div className={shellClass(sport)}><div className="page-container is-wide">
    <GameCrumb sport={sport} to={to} />
    <header className="game-head">
      <h1 className="game-head__title">{title}</h1>
      {hero}
      <p className="game-head__meta">{meta.join(' · ')}</p>
    </header>
    {notice}
    <Tabs key={tabsKey} className="nfl-game-tabs" defaultActiveKey="props" destroyOnHidden aria-label="Game sections" animated={false}
      items={[{ key: 'matchup', label: 'Matchup', children: matchup }, { key: 'props', label: 'Player Props', children: props }]} />
  </div></div>
}

/** Loading, error and not-found pages: the same crumb, with a placeholder head. */
export function GamePageState({ sport, children }: { sport: GameSport, children: ReactNode }) {
  return <div className={shellClass(sport)}><div className="page-container is-wide">
    <GameCrumb sport={sport} />
    <PageHead title={`${sport.toUpperCase()} game`} />
    {children}
  </div></div>
}

export function GameNotFound({ sport, reason }: { sport: GameSport, reason: string }) {
  return <GamePageState sport={sport}><p className="nfl-game-empty is-page">Game not found. {reason}</p></GamePageState>
}
