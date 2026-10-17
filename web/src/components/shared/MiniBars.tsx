import type { CSSProperties } from 'react'
import type { NflRecentBar, NflRecentBars } from '~/utils/nflPropCards'
import './prop-table.css'

interface Props {
  bars: NflRecentBars
  title: (bar: NflRecentBar) => string
  empty: string
}

/** Last games, oldest to newest, on one scale with the line; the dashed mark is the line. Grayscale only. */
export function MiniBars({ bars: { bars, linePct }, title, empty }: Props) {
  if (!bars.length) return <span className="mini-bars__empty">{empty}</span>
  const style = linePct === null ? undefined : { '--line': `${linePct}%` } as CSSProperties
  return <span className={`mini-bars${linePct === null ? '' : ' has-line'}`} style={style} aria-label={`Last ${bars.length} games`}>
    {bars.map((bar, index) => <span key={index} className={`is-${bar.vsLine ?? 'none'}`} style={{ '--h': `${bar.heightPct}%` } as CSSProperties} title={title(bar)} />)}
  </span>
}
