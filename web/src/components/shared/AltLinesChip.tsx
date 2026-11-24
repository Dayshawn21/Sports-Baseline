import { Popover } from 'antd'
import { useState } from 'react'
import './prop-table.css'

interface Props {
  /** Each alternate line as the row would print it, in board order. */
  labels: readonly string[]
  /** Names the line in the popover title and the button's label, e.g. "Points". */
  context: string
}

/** The alternates behind a `+N alts` chip, so a row keeps to its main line. Renders nothing without alternates. */
export function AltLinesChip({ labels, context }: Props) {
  const [open, setOpen] = useState(false)
  if (!labels.length) return null
  const count = `${labels.length} alt${labels.length === 1 ? '' : 's'}`
  return <Popover open={open} onOpenChange={setOpen} trigger="click" title={`${context}: ${count}`}
    content={<ul className="alt-lines" onClick={event => event.stopPropagation()}>
      {labels.map((label, index) => <li key={index}>{label}</li>)}
    </ul>}>
    {/* The row navigates on click, so the chip keeps its clicks and keys to itself. */}
    <button type="button" className="alt-lines-chip" aria-expanded={open} aria-label={`${count} for ${context}: ${labels.join(', ')}`}
      onClick={event => event.stopPropagation()} onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); event.stopPropagation() } }}>
      +{count}
    </button>
  </Popover>
}
