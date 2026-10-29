import { Tooltip } from 'antd'
import { Link } from 'react-router-dom'
import type { CSSProperties, MouseEvent, ReactNode } from 'react'
import type { TennisBoardCategory, TennisBoardLine } from '~/utils/tennisPropBoard'
import { propCard, type TennisPropCardModel } from '~/utils/tennisPropCards'
import { tourTone } from '~/utils/tennisSlate'
import { propMatchPath } from '~/utils/tennisMatchView'
import '~/components/shared/prop-table.css'
import '~/components/tennis/tennis-slate.css'
import './tennis-prop-table.css'

const OTHER_LINES_NOTE = 'Not rated. These are unpriced, ungraded, or have missing, stale, unsupported or thin-sample data. View evidence for each line\'s context.'

/** Tennis lines are gray and unranked (48f): a row is rated or for review, never numbered. */
export interface TennisPropTableRow {
  row: TennisBoardLine
  rated: boolean
}

function Player({ card, selected, onOpen, matchPath }: { card: TennisPropCardModel, selected: boolean, onOpen: () => void, matchPath: string | null }) {
  const tone = tourTone(card.tour, card.tour)
  return <>
    <span className="prop-table__player-name">
      {matchPath ? <Link className="prop-table__open" to={matchPath} aria-label={`Open picks and props for ${card.playerName}`}>{card.playerName}</Link>
        : <button type="button" className="prop-table__open" aria-pressed={selected} aria-haspopup="dialog" aria-label={`View evidence for ${card.playerName}`} onClick={onOpen}>{card.playerName}</button>}
      {tone && <span className={`tennis-tour-tag is-${tone}`}>{card.tour}</span>}
    </span>
    <small title={card.meta}>{card.meta || 'Match unavailable'}</small>
    <small className="tennis-prop-table__start">{card.startText}</small>
  </>
}

function Line({ card }: { card: TennisPropCardModel }) {
  const side = card.pickTone === 'positive' ? '' : ` is-${card.pickTone}`
  const payout = card.payoutTier ? ` · ${card.payoutTier}` : ''
  return <>
    <span className={`tennis-prop-table__pick${side}`}>{card.pickLabel}</span>{' '}
    <b className="tennis-prop-table__line-value">{card.valueText}</b>
    <small>{card.valueLabel} · {card.source}{payout}</small>
  </>
}

function HitAgainstBreakEven({ card }: { card: TennisPropCardModel }) {
  const hasComparison = card.hitPct != null && card.breakEvenPct != null
  const style = hasComparison
    ? { '--p': `${card.hitPct}%`, '--be': `${card.breakEvenPct}%` } as CSSProperties
    : undefined
  return <>
    <span>{card.hitPct == null ? '--' : `${card.hitPct.toFixed(0)}%`}</span>
    {hasComparison && <span className="tennis-prop-table__prob" style={style}><span /></span>}
    <small>{card.breakEvenLabel ?? 'Break-even --'}</small>
  </>
}

function Trust({ card }: { card: TennisPropCardModel }) {
  return <>
    <span className="tennis-prop-table__mobile-gap">{card.gapText ?? '--'} · </span>
    <span className={`tennis-prop-table__trust${card.flags.length ? ' is-flagged' : ''}`}>{card.trust}</span>
    <Tooltip title={card.flags.length ? card.flags.join(' · ') : 'No quality notes'}>
      <small>{card.sampleText}</small>
    </Tooltip>
  </>
}

function PropRow({ item: { row, rated }, selected, onOpen, showMatchLinks }: { item: TennisPropTableRow, selected: boolean, onOpen: (row: TennisBoardLine) => void, showMatchLinks: boolean }) {
  const card = propCard(row)
  const classes = ['is-row', selected && 'is-selected', !rated && 'is-dim'].filter(Boolean).join(' ')
  const open = (event: MouseEvent) => { if (!(event.target instanceof Element && event.target.closest('button, a'))) onOpen(row) }
  return <tr className={classes} onClick={open}>
    <td className="prop-table__player"><Player card={card} selected={selected} onOpen={() => onOpen(row)} matchPath={showMatchLinks ? propMatchPath(row) : null} /></td>
    <td className="tennis-prop-table__line"><Line card={card} /></td>
    <td className="is-num" data-label="model">{card.projectionText}</td>
    <td className="is-num tennis-prop-table__gap" data-label="gap">{card.gapText ?? '--'}</td>
    <td className="tennis-prop-table__hit" data-label="P(over)"><HitAgainstBreakEven card={card} /></td>
    <td className={`prop-table__end is-num tennis-prop-table__ev${card.evTone ? ` is-${card.evTone}` : ''}`} data-label="EV">{card.evText}</td>
    <td><Trust card={card} /><button type="button" className="tennis-prop-text-action tennis-prop-table__evidence" aria-haspopup="dialog" aria-label={`View evidence for ${card.playerName}, ${row.statType.replaceAll('_', ' ')}, ${card.valueText}`} onClick={() => onOpen(row)}>View evidence</button></td>
  </tr>
}

const COLUMNS: Array<[string, ReactNode]> = [
  ['player', 'Player'], ['line', 'Line'], ['model', 'Model'], ['gap', 'Gap'],
  ['hit', 'P(over) / BE'], ['ev', 'EV'], ['trust', 'Trust'],
]
const NUMERIC = new Set(['model', 'gap', 'ev'])

interface Props {
  showMatchLinks?: boolean
  tableId?: string
  category: TennisBoardCategory
  rateable: TennisPropTableRow[]
  other: TennisPropTableRow[]
  selectedId: number | null
  onOpen: (row: TennisBoardLine) => void
}

/** One market's tennis lines in board order: rated lines, then lines for review. */
export function TennisPropTable({ category, rateable, other, selectedId, onOpen, tableId = 'tennis-prop-lines', showMatchLinks = true }: Props) {
  const renderRow = (item: TennisPropTableRow) => <PropRow key={`${item.row.source}-${item.row.id}`} item={item} selected={item.row.id === selectedId} onOpen={onOpen} showMatchLinks={showMatchLinks} />
  return <table id={tableId} className="prop-table tennis-prop-table" aria-label={`${category.label} lines`}>
    <colgroup>{COLUMNS.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{COLUMNS.map(([key, label]) => <th key={key} className={NUMERIC.has(key) ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>
      {rateable.map(renderRow)}
      {other.length > 0 && <tr className="prop-table__divider"><td colSpan={COLUMNS.length}><strong>Lines for review</strong><small>{OTHER_LINES_NOTE}</small></td></tr>}
      {other.map(renderRow)}
    </tbody>
  </table>
}
