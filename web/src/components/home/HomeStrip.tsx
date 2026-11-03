import { Link } from 'react-router-dom'
import type { HomeView } from '~/hooks/useHomeData'
import { SPORTS, sportViews } from '~/utils/sportNav'
import './home.css'

/** The other sports, soonest start first; a failed sport offers a retry in place of its link. */
export function HomeStrip({ rows }: { rows: HomeView['strip'] }) {
  return <div className="home-strip">
    {rows.map(row => {
      const label = SPORTS.find(entry => entry.code === row.sport)!.label
      const content = <><b>{label}</b><span>{row.text}</span></>
      return row.tone === 'error'
        ? <div key={row.sport} className="home-strip__row is-error">{content}
          <button type="button" onClick={row.retry}>Retry</button></div>
        : <Link key={row.sport} to={sportViews(row.sport)[0].path} className={`home-strip__row${row.tone === 'quiet' ? ' is-quiet' : ''}`}>{content}</Link>
    })}
  </div>
}
