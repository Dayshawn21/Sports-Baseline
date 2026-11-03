import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { marketCountLabel } from '~/utils/playerPage'
import '~/pages/nfl-player.css'

export const TABS_ID = 'prop-tabs'

interface Props {
  heading: string
  /** Replaces the market count beside the heading, for a page that counts something else. */
  note?: string
  tabs: Array<{ key: string, label: string }>
  /** -1 when no tab is selected. */
  selectedIndex: number
  hrefFor: (key: string) => string
  /** The selected market's section. */
  children?: ReactNode
}

/** The player page's market tab strip; each sport decides its tabs and links, the frame is the same. */
export function PlayerMarketTabs({ heading, note, tabs, selectedIndex, hrefFor, children }: Props) {
  if (tabs.length === 0) return null
  return <>
    <h2 className="nfl-player-section-title">{heading} <small>{note ?? marketCountLabel(tabs.length)}</small></h2>
    <nav id={TABS_ID} className="nfl-player-jump" aria-label="Choose a prop">
      {tabs.map((tab, position) => <Link key={tab.key} to={hrefFor(tab.key)} replace
        aria-current={position === selectedIndex ? 'true' : undefined}>{tab.label}</Link>)}
    </nav>
    {children}
  </>
}
