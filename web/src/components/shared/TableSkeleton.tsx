import type { CSSProperties } from 'react'
import { skeletonWidths } from '~/utils/skeleton'
import './table-skeleton.css'

interface Props {
  /** Read to screen readers in place of the old visible loading message. */
  label: string
  columns: number
  rows?: number
  /** Desktop row height in px, matched to the loaded table. */
  rowHeight?: number
  /** Row height in px once the table stacks each row (1100px and below). */
  stackedRowHeight?: number
  /** Boards keep their card box on phones; slates drop it. */
  variant?: 'slate' | 'board'
}

export default function TableSkeleton({ label, columns, rows = 8, rowHeight = 53, stackedRowHeight = 77, variant = 'slate' }: Props) {
  const widths = skeletonWidths(rows, columns)
  const style = {
    '--skeleton-columns': columns,
    '--skeleton-row': `${rowHeight}px`,
    '--skeleton-row-stacked': `${stackedRowHeight}px`,
  } as CSSProperties
  return (
    <div className={`table-skeleton is-${variant}`} role="status" aria-busy="true" style={style}>
      <span className="table-skeleton__label">{label}</span>
      <div className="table-skeleton__title" aria-hidden="true"><span className="table-skeleton__bar" /></div>
      <div className="table-skeleton__head" aria-hidden="true">
        {Array.from({ length: columns }, (_, column) => <span key={column} className="table-skeleton__bar" />)}
      </div>
      {widths.map((row, index) => (
        <div key={index} className="table-skeleton__row" aria-hidden="true">
          {row.map((width, column) => <span key={column} className="table-skeleton__bar" style={{ width: `${width}%` }} />)}
        </div>
      ))}
    </div>
  )
}
