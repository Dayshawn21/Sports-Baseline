import { Tooltip } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import type { MouseEvent, ReactNode } from 'react'
import { ProbabilityRing } from '~/components/shared/ProbabilityRing'
import type { TennisBoardCategory, TennisBoardLine } from '~/utils/tennisPropBoard'
import { propCard, type TennisPropCardModel } from '~/utils/tennisPropCards'
import { tourTone } from '~/utils/tennisSlate'
import { probabilityRing, tennisRowSignal, type RowSignal } from '~/utils/propRowVisuals'
import '~/components/shared/prop-table.css'
import '~/components/tennis/tennis-slate.css'
import './tennis-prop-table.css'
import { Fragment, useState } from 'react'
import { TennisPropReasons } from '~/components/tennis/TennisPropReasons'
import { hasReasons } from '~/utils/tennisPropReasons'

const OTHER_LINES_NOTE = "Not rated. These are unpriced, ungraded, or have missing, stale, unsupported or thin-sample data. Open the player for each line's context."

/** Tennis lines are gray and unranked unless adopted (48f, 48g): a row is rated or for review, never numbered. */
export interface TennisPropTableRow {
  row: TennisBoardLine
  rated: boolean
}

function Player({ card, path, from }: { card: TennisPropCardModel, path: string | null, from: string }) {
  const tone = tourTone(card.tour, card.tour)
  return <>
    <span className="prop-table__player-name">
      {path ? <Link className="prop-table__open" to={path} state={{ from }} aria-label={`Open ${card.playerName}'s page`}>{card.playerName}</Link>
        : <span className="prop-table__open">{card.playerName}</span>}
      {tone && <span className={`tennis-tour-tag is-${tone}`}>{card.tour}</span>}
    </span>
    <small title={card.meta}>{card.meta || 'Match unavailable'}</small>
    <small className="tennis-prop-table__start">{card.startText}</small>
  </>
}

function Line({ card }: { card: TennisPropCardModel }) {
  // A PrizePicks row names its playable sides, not a pick, so it stays gray (48f)
  // unless 48e adopted its slice (48g); an adopted under is a pick, not a negative.
  const unadopted = card.pickLabel === '--' || card.payoutTier ? ' is-none' : card.isUnder ? ' is-negative' : ''
  const side = card.adopted ? '' : unadopted
  const payout = card.payoutTier ? ` · ${card.payoutTier}` : ''
  return <>
    <span className={`tennis-prop-table__pick${side}`}>{card.pickLabel}</span>{' '}
    <b className="tennis-prop-table__line-value">{card.valueText}</b>
    <small>{card.valueLabel} · {card.source}{payout}</small>
  </>
}

function HitAgainstBreakEven({ card, signal }: { card: TennisPropCardModel, signal: RowSignal }) {
  return <>
    <span><ProbabilityRing ring={probabilityRing(card.hitPct, signal, card.breakEvenPct)} />{card.hitPct == null ? '--' : `${card.hitPct.toFixed(0)}%`}</span>
    <small>{card.breakEvenLabel ?? 'Break-even --'}</small>
    {card.marginText && <small className="tennis-prop-table__margin">{card.marginText}</small>}
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

interface PropRowProps {
  item: TennisPropTableRow
  path: string | null
  from: string
  /** The Why over / Why under toggle; null for a row the panel cannot explain. */
  reasons: { open: boolean, panelId: string, onToggle: () => void } | null
}

function PropRow({ item: { row, rated }, path, from, reasons }: PropRowProps) {
  const navigate = useNavigate()
  const card = propCard(row)
  const classes = [path && 'is-row', !rated && 'is-dim'].filter(Boolean).join(' ')
  // Links keep their native behavior, including modified clicks.
  const onRowClick = (event: MouseEvent) => {
    if (!path || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    if (event.target instanceof Element && event.target.closest('a, button')) return
    navigate(path, { state: { from } })
  }
  const market = row.statType.replaceAll('_', ' ')
  return <tr className={classes} onClick={onRowClick}>
    <td className="prop-table__player"><Player card={card} path={path} from={from} /></td>
    <td className="tennis-prop-table__line"><Line card={card} /></td>
    <td className="is-num" data-label="model">{card.projectionText}</td>
    <td className="is-num tennis-prop-table__gap" data-label="gap">{card.gapText ?? '--'}</td>
    <td className="tennis-prop-table__hit" data-label="P(over)"><HitAgainstBreakEven card={card} signal={tennisRowSignal(row)} /></td>
    <td className={`prop-table__end is-num tennis-prop-table__ev${card.evTone ? ` is-${card.evTone}` : ''}`} data-label="EV">{card.evText}</td>
    <td><Trust card={card} />
      {path && <Link to={path} state={{ from }} className="tennis-prop-text-action tennis-prop-table__evidence" aria-label={`Open ${card.playerName}'s page, ${market}, ${card.valueText}`}>Open player</Link>}
      {reasons && <button type="button" className="tennis-prop-text-action tennis-prop-table__reasons-toggle" onClick={reasons.onToggle}
        aria-expanded={reasons.open} aria-controls={reasons.open ? reasons.panelId : undefined}
        aria-label={`${reasons.open ? 'Hide' : 'Show'} why ${card.playerName}'s ${market} ${card.valueText} could go over or under`}>
        {reasons.open ? 'Hide why' : 'Why over / under'}
      </button>}
    </td>
  </tr>
}

const COLUMNS: Array<[string, ReactNode]> = [
  ['player', 'Player'], ['line', 'Line'], ['model', 'Model'], ['gap', 'Gap'],
  ['hit', 'P(over) / BE'], ['ev', 'EV'], ['trust', 'Trust'],
]
const NUMERIC = new Set(['model', 'gap', 'ev'])

interface Props {
  tableId?: string
  category: TennisBoardCategory
  rateable: TennisPropTableRow[]
  other: TennisPropTableRow[]
  /** Where a row opens; null leaves it unlinked. */
  pathFor: (row: TennisBoardLine) => string | null
  /** The page the rows are on, so the player page can link back. */
  from: string
}

/** One market's tennis lines in board order: rated lines, then lines for review. */
export function TennisPropTable({ category, rateable, other, pathFor, from, tableId = 'tennis-prop-lines' }: Props) {
  // Open panels belong to one market, so switching markets closes them.
  const [open, setOpen] = useState<{ market: string, keys: ReadonlySet<string> }>({ market: category.market, keys: new Set() })
  const openKeys = open.market === category.market ? open.keys : new Set<string>()
  const toggle = (key: string) => {
    const keys = new Set(openKeys)
    if (!keys.delete(key)) keys.add(key)
    setOpen({ market: category.market, keys })
  }
  const renderRow = (item: TennisPropTableRow) => {
    const key = `${item.row.source}-${item.row.id}`
    const panelId = `${tableId}-reasons-${item.row.id}`
    const isOpen = openKeys.has(key)
    return <Fragment key={key}>
      <PropRow item={item} path={pathFor(item.row)} from={from}
        reasons={hasReasons(item.row) ? { open: isOpen, panelId, onToggle: () => toggle(key) } : null} />
      {isOpen && <tr className="tennis-prop-table__reasons-row" id={panelId}>
        <td colSpan={COLUMNS.length}><TennisPropReasons propId={item.row.id} /></td>
      </tr>}
    </Fragment>
  }
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
