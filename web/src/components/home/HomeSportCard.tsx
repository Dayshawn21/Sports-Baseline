import { Link } from 'react-router-dom'
import type { HomeCard } from '~/utils/home'
import './home.css'

/** One sport. The title link covers the card (so the whole card opens the slate) and each view link sits above it. */
export function HomeSportCard({ card, onRetry }: { card: HomeCard, onRetry: () => void }) {
  const slate = card.links[0]
  return <article className={`home-card is-${card.tone}`}>
    <div className="home-card__name">
      <Link to={slate.path}>{card.label}</Link>
      <span>{card.period}</span>
    </div>
    <p className="home-card__when">{card.when}</p>
    <div className="home-card__big">{card.count}<small>{card.noun}</small></div>
    {card.next && <p className="home-card__next">{card.next}</p>}
    <div className="home-card__links">
      {card.links.map(link => <Link key={link.view} to={link.path}>{link.label}</Link>)}
      {card.tone === 'error' && <button type="button" onClick={onRetry}>Retry</button>}
    </div>
  </article>
}
