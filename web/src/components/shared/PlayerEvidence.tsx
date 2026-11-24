import type { ReactNode } from 'react'
import './player-evidence.css'

/** The panel's supporting detail, closed by default so the projection, form and lines lead. `contents` names what is inside. */
export function PlayerEvidence({ contents, children }: { contents: string, children: ReactNode }) {
  return <details className="player-evidence">
    <summary><span className="player-evidence__title">Evidence</span><span className="player-evidence__contents">{contents}</span></summary>
    <div className="player-evidence__body">{children}</div>
  </details>
}
