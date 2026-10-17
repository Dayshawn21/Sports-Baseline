import { Link, useLocation } from 'react-router-dom'
import { sportViews, sportViewForPath, type Sport, type SportView } from '~/utils/sportNav'

const VIEW_LABELS: Record<SportView, string> = { slate: 'Slate', props: 'Props', model: 'Model' }

export default function SportViewSwitch({ sport }: { sport: Sport }) {
  const active = sportViewForPath(useLocation().pathname)
  return <nav className="sport-view-switch" aria-label="Sport views">
    {sportViews(sport).map(({ view, path }) => <Link
      key={view}
      to={path}
      className={view === active ? 'is-selected' : ''}
      aria-current={view === active ? 'page' : undefined}
    >{VIEW_LABELS[view]}</Link>)}
  </nav>
}
