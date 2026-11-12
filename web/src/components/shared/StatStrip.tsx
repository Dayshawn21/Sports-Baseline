import type { StatCell } from '~/utils/propRowVisuals'
import './prop-table.css'

/** The row's recent-game cells, label over value, in one compact line under its bars. Renders nothing without cells. */
export function StatStrip({ cells }: { cells: readonly StatCell[] }) {
  if (!cells.length) return null
  return <dl className="stat-strip">
    {cells.map(cell => <div key={cell.key} className={cell.tone === 'neutral' ? undefined : `is-tone-${cell.tone}`}>
      <dt>{cell.label}</dt>
      <dd>{cell.value}</dd>
    </div>)}
  </dl>
}
