import { Popover } from 'antd'
import { useState, type CSSProperties } from 'react'
import type { NflRecentBar, NflRecentBars } from '~/utils/nflPropCards'
import './prop-table.css'

interface Props {
  bars: NflRecentBars
  title: (bar: NflRecentBar) => string
  empty: string
  interactive?: boolean
  valueLabel?: (bar: NflRecentBar) => string
  lineLabel?: string
  showOpponents?: boolean
}

/** Last games, oldest to newest, on one scale with the line; the dashed mark is the line. Grayscale only. */
export function MiniBars({ bars: { bars, linePct }, title, empty, interactive = false, valueLabel, lineLabel, showOpponents = false }: Props) {
  const [open, setOpen] = useState(false)
  if (!bars.length) return <span className="mini-bars__empty">{empty}</span>
  const style = linePct === null ? undefined : { '--line': `${linePct}%` } as CSSProperties
  const chart = <span className={`mini-bars${linePct === null ? '' : ' has-line'}${valueLabel ? ' has-values' : ''}`} style={style} aria-label={interactive ? undefined : `Last ${bars.length} games`} aria-hidden={interactive || undefined}>
    {bars.map((bar, index) => <span key={index} className={`is-${bar.vsLine ?? 'none'}`} style={{ '--h': `${bar.heightPct}%` } as CSSProperties} title={title(bar)}>
      {valueLabel && <span className="mini-bars__value">{valueLabel(bar)}</span>}
    </span>)}
  </span>
  const labeledChart = <span className={`mini-bars-group${valueLabel ? ' has-values' : ''}`}>
    {linePct !== null && lineLabel && <span className="mini-bars__caption">Line {lineLabel}</span>}
    {chart}
    {showOpponents && <span className="mini-bars__opponents" aria-hidden="true">{bars.map((bar, index) => <span key={index}>{bar.opponentTeam ?? '--'}</span>)}</span>}
  </span>
  if (!interactive) return labeledChart
  return <Popover open={open} onOpenChange={setOpen} trigger="click" title={`Last ${bars.length} games`}
    content={<div className="mini-bars-history" onClick={event => event.stopPropagation()}>
      <p>Oldest to newest</p>
      <ol>{bars.map((bar, index) => <li key={index}>{title(bar)}</li>)}</ol>
      {linePct !== null && <p>The dashed mark is the current line.</p>}
    </div>}>
    <button type="button" className="mini-bars-button" aria-expanded={open}
      aria-label={`View last ${bars.length} games, oldest to newest: ${bars.map(title).join('; ')}`}
      onClick={event => event.stopPropagation()} onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); event.stopPropagation() } }}>
      {labeledChart}
    </button>
  </Popover>
}
