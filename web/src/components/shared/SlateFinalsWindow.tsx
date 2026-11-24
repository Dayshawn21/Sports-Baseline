import { type ReactNode, useId, useState } from 'react'
import '~/pages/nfl-slate.css'

interface SlateFinalsWindowProps {
  /** "13 games", or "2 of 13 games" while a search narrows it. */
  subtitle: string
  /** Read once: the parent keys this window by period and search, so a new week or search starts it afresh. */
  startOpen: boolean
  children: ReactNode
}

/** Every finished game in one window, closed by default so what is still in play reaches the first screen. */
export default function SlateFinalsWindow({ subtitle, startOpen, children }: SlateFinalsWindowProps) {
  const [open, setOpen] = useState(startOpen)
  const bodyId = useId()
  return <section className={`nfl-slate-window slate-finals${open ? ' is-open' : ''}`} aria-label="Final games">
    <h2 className="nfl-slate-window__title">
      <button type="button" className="slate-finals__toggle" aria-expanded={open} aria-controls={bodyId} onClick={() => setOpen(!open)}>
        <span className="slate-finals__chevron" aria-hidden="true" />
        Final <small>{subtitle}</small>
      </button>
    </h2>
    <div id={bodyId} hidden={!open}>{children}</div>
  </section>
}
