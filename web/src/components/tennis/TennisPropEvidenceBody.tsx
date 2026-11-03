import { Tag } from 'antd'
import { Link } from 'react-router-dom'
import type { CSSProperties, ReactNode, Ref } from 'react'
import type { TennisBoardLine } from '~/utils/tennisPropBoard'
import { marketLabel, signalSummary, sourceLabel } from '~/utils/tennisPropBoard'
import { propCard, type RecentStatBar } from '~/utils/tennisPropCards'
import { propMatchPath } from '~/utils/tennisMatchView'

function flagLabel(flag: string): string {
  return flag.replaceAll('_', ' ')
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(`${value}T12:00:00`))
}

interface RecentBarsChartProps {
  title: string
  line: number
  bars: RecentStatBar[]
}

/** Recent box-score values against today's line; no rate or count on purpose. */
export function TennisRecentBars({ title, line, bars }: RecentBarsChartProps) {
  const scale = Math.max(line, ...bars.map(bar => bar.value ?? 0)) * 1.15 || 1
  const columns: CSSProperties = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` }
  const summary = bars.map(bar => bar.value ?? 'no data').join(', ')
  return <section className="tennis-prop-form tennis-prop-bars">
    <span>{title}</span>
    <div className="tennis-prop-bars__values" style={columns} aria-hidden="true">{bars.map((bar, index) => <em key={`${bar.matchDate}-${index}`}>{bar.value ?? '--'}</em>)}</div>
    <div className="tennis-prop-bars__chart" role="img" aria-label={`Oldest to newest: ${summary}, against the ${line.toFixed(1)} line`} style={{ ...columns, '--line': `${(line / scale) * 100}%` } as CSSProperties}>
      {bars.map((bar, index) => <i key={`${bar.matchDate}-${index}`} className={bar.vsLine ? `is-${bar.vsLine}` : 'is-missing'} style={{ '--h': `${((bar.value ?? 0) / scale) * 100}%` } as CSSProperties} />)}
    </div>
    <div className="tennis-prop-bars__dates" style={columns} aria-hidden="true">{bars.map((bar, index) => <small key={`${bar.matchDate}-${index}`} title={`vs ${bar.opponentName}`}>{dateLabel(bar.matchDate)}</small>)}</div>
    <small className="tennis-prop-bars__line">Dashed line: today's {line.toFixed(1)} line</small>
  </section>
}

function LineSummary({ row }: { row: TennisBoardLine }) {
  const card = propCard(row)
  const unadopted = card.pickLabel === '--' || card.payoutTier ? ' is-none' : card.isUnder ? ' is-negative' : ''
  const side = card.adopted ? '' : unadopted
  return <>
    <p>{row.matchup ?? 'Match unavailable'}</p>
    <p>{card.startText}</p>
    <div className="tennis-prop-evidence__summary">
      <span className={`tennis-prop-evidence__pick${side}`}>{card.pickLabel}</span>
      <b>{card.valueText}</b>
      {card.marginText && <span className="tennis-prop-evidence__margin">{card.marginText}</span>}
      {card.evText !== '--' && <span className={`tennis-prop-evidence__ev${card.evTone ? ` is-${card.evTone}` : ''}`}>{card.evText} EV</span>}
    </div>
  </>
}

function ContextFacts({ row }: { row: TennisBoardLine }) {
  const opponent = row.opponentStatAvg == null ? 'Unavailable' : `${row.opponentStatAvg.toFixed(1)} avg${row.opponentMatchesCount ? ` · ${row.opponentMatchesCount} matches` : ''}`
  return <div className="tennis-prop-evidence__grid">
    <div><span>Event</span><strong>{[row.tournament, row.surface].filter(Boolean).join(' · ') || 'Unavailable'}</strong></div>
    <div><span>Opponent allows</span><strong>{opponent}</strong></div>
    <div><span>Projection basis</span><strong>{row.projectionSource?.replaceAll('_', ' ') ?? 'Rolling player stats'}</strong></div>
  </div>
}

interface EvidenceBodyProps {
  row: TennisBoardLine
  ref?: Ref<HTMLElement>
  /** Rendered between the projection inputs and the quality notes. */
  children?: ReactNode
}

export function TennisPropEvidenceBody({ row, ref, children }: EvidenceBodyProps) {
  const flags = row.dataQualityFlags ?? []
  const inputs = Object.entries(row.projectionInputs ?? {})
  const matchPath = propMatchPath(row)
  return <aside ref={ref} className="tennis-prop-evidence" aria-label={`Evidence for ${row.playerName ?? 'selected prop'}`}>
    <header>
      <h2>{row.playerName ?? 'Unknown player'}</h2>
      <p>{marketLabel(row.statType)} · {sourceLabel(row.source)}</p>
      <LineSummary row={row} />
      {matchPath && <Link to={matchPath} className="tennis-prop-text-action">Open match picks &amp; props</Link>}
    </header>
    <section className="tennis-prop-evidence__reason"><span>Why this signal</span><p>{signalSummary(row)}</p></section>
    <ContextFacts row={row} />
    {inputs.length > 0 && <section className="tennis-prop-evidence__inputs"><span>Projection inputs</span><div>{inputs.map(([key, value]) => <Tag key={key}>{key.replaceAll('_', ' ')}: {typeof value === 'number' ? value.toFixed(2) : value}</Tag>)}</div></section>}
    {children}
    {flags.length > 0 && <section className="tennis-prop-evidence__inputs"><span>Quality notes</span><div>{flags.map(flag => <Tag key={flag}>{flagLabel(flag)}</Tag>)}</div></section>}
  </aside>
}
