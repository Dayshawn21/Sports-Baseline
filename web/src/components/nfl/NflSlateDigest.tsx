import { Link } from 'react-router-dom'
import type { NflSlateDigestItem } from '~/utils/nflSlate'
import './nfl-slate-digest.css'

/** The week's largest prop gaps; gray reference, never a pick until the ranking check adopts a slice. */
export function NflSlateDigest({ items }: { items: NflSlateDigestItem[] }) {
  if (items.length === 0) return null
  return <section className="nfl-slate-digest" aria-labelledby="nfl-slate-digest-label">
    <h2 id="nfl-slate-digest-label" className="nfl-slate-digest__label">Largest gaps this week · reference, not picks</h2>
    <div className="nfl-slate-digest__plays">
      {items.map(item => <Link key={item.lineId} className="nfl-slate-digest__play" to={`/nfl/game/${item.gameId}`}
        aria-label={`${item.playerName}, ${item.market}, ${item.matchup}, open game page`}>
        <strong>{item.playerName}</strong>
        <span className="nfl-slate-digest__what">{item.market} · {item.matchup}</span>
        <span className="nfl-slate-digest__num"><span>line {item.line}</span><span>model {item.model}</span></span>
        <span className="nfl-slate-digest__gap">gap {item.gap}</span>
      </Link>)}
    </div>
  </section>
}
