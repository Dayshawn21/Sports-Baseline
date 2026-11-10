import { Tag } from 'antd'
import { Fragment, type ReactNode } from 'react'
import { payoutTierNote } from '~/utils/playerPage'
import './player-panel.css'

export type PlayerLinesColumn = 'gap' | 'pOver' | 'pUnder'

export interface PlayerLinesCell {
  content: ReactNode
  className?: string
}

export interface PlayerLinesRow {
  key: string
  type: string
  /** Under the type tag, such as tennis's "review". */
  typeNote?: string
  line: string
  gap?: string
  pOver?: ReactNode
  pUnder?: string
  trailing?: PlayerLinesCell[]
  selected?: boolean
  /** A full-width note under the row, such as an NBA probability caveat. */
  note?: string | null
  propId?: string | number
}

interface PlayerLinesTableProps {
  title?: string
  /** Which core columns this market has; they always appear in the order Gap, P(over), P(under). */
  columns: PlayerLinesColumn[]
  /** Headers for sport-specific columns after the core ones. */
  trailing?: string[]
  rows: PlayerLinesRow[]
  /** Above the table, such as a caption on what P(over) means. */
  intro?: ReactNode
  /** Below the table, such as a reference-only note. */
  children?: ReactNode
}

const CORE: Array<{ key: PlayerLinesColumn, label: string }> = [
  { key: 'gap', label: 'Gap' }, { key: 'pOver', label: 'P(over)' }, { key: 'pUnder', label: 'P(under)' },
]

/** The lines on offer for one market, the same on every player page. The type tag is always gray: a goblin or demon line is a payout tier, not a signal. */
export function PlayerLinesTable({ title = 'PrizePicks lines', columns, trailing = [], rows, intro, children }: PlayerLinesTableProps) {
  const core = CORE.filter(column => columns.includes(column.key))
  const span = 2 + core.length + trailing.length
  const tierNote = payoutTierNote(rows.map(row => row.type))
  return <section className="nfl-prop-detail__section">
    <div className="nfl-prop-detail__section-head"><h3>{title}</h3></div>
    {intro}
    <div className="player-lines__wrap">
      <table className="nfl-prop-detail__table">
        <thead><tr>
          <th>Type</th><th>Line</th>
          {core.map(column => <th key={column.key}>{column.label}</th>)}
          {trailing.map(label => <th key={label}>{label}</th>)}
        </tr></thead>
        <tbody>{rows.map(row => <Fragment key={row.key}>
          <tr data-prop-id={row.propId} className={row.selected ? 'is-selected' : undefined}>
            <td>
              <Tag>{row.type}</Tag>
              {row.selected && <span className="nfl-prop-detail__this">This line</span>}
              {row.typeNote && <small>{row.typeNote}</small>}
            </td>
            <td>{row.line}</td>
            {core.map(column => <td key={column.key}>{row[column.key] ?? '--'}</td>)}
            {row.trailing?.map((cell, index) => <td key={index} className={cell.className}>{cell.content}</td>)}
          </tr>
          {row.note && <tr className="player-lines__note"><td colSpan={span}>{row.note}</td></tr>}
        </Fragment>)}</tbody>
      </table>
    </div>
    {tierNote && <p className="player-lines__tier-note">{tierNote}</p>}
    {children}
  </section>
}
