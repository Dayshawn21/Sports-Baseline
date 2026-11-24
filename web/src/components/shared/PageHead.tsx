import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

/** Previous and next are paths; null or missing renders the control disabled. The picker sits between them. */
export interface PageHeadPeriod { label: string, previous?: string | null, next?: string | null, picker?: ReactNode }

interface PageHeadProps {
  title: string
  /** The period line beside the title: the period the page covers and its counts (57a). */
  meta?: ReactNode
  period?: PageHeadPeriod
  actions?: ReactNode
  stats?: ReactNode
}

function PeriodLink({ to, children }: { to: string | null | undefined, children: ReactNode }) {
  return to
    ? <Link className="page-head-period__link" to={to}>{children}</Link>
    : <span className="page-head-period__link" aria-disabled="true">{children}</span>
}

/** The one page head every sport page shares (38a): title block, period and page controls, then the stats strip. */
export default function PageHead({ title, meta, period, actions, stats }: PageHeadProps) {
  return <header className="lf-page-head">
    <div className="lf-page-head__row">
      <div className="lf-page-head__text">
        <h1 className="unified-page-title">{title}</h1>
        {meta && <p className="lf-page-head__meta">{meta}</p>}
      </div>
      {(period || actions) && <div className="lf-page-head__controls">
        {period && <nav className="page-head-period" aria-label={period.label}>
          <PeriodLink to={period.previous}>← Previous</PeriodLink>
          {period.picker && <div className="page-head-period__picker">{period.picker}</div>}
          <PeriodLink to={period.next}>Next →</PeriodLink>
        </nav>}
        {actions}
      </div>}
    </div>
    {stats && <div className="lf-page-head__stats">{stats}</div>}
  </header>
}
