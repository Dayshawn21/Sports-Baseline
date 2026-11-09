import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
// Tennis does not load the slate stylesheet otherwise; its selectors are all scoped to slate classes.
import '~/pages/nfl-slate.css'

/** `text` is a node so a part can hold a control (57d puts the tennis prop-source select there). */
export interface SlateLegendProps { parts: { label: string, text: ReactNode }[], pick: string[] }

/** The one-line legend every slate shares (57b): source and cadence, then a "What's a pick?" disclosure. */
export default function SlateLegend({ parts, pick }: SlateLegendProps) {
  return <div className="nfl-slate__legend slate-legend">
    {parts.map(part => <span key={part.label}><b>{part.label}</b> {part.text}</span>)}
    <details className="slate-legend__pick">
      <summary>What&apos;s a pick?</summary>
      <p>{pick.join(' ')} <Link to="/how-it-works">How it works →</Link></p>
    </details>
  </div>
}
