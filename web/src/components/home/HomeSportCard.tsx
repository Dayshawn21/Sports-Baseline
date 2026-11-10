import { Link } from 'react-router-dom'
import TeamLogo from '~/components/shared/TeamLogo'
import type { HomeCard, HomeNextSegment } from '~/utils/home'
import { isLogoSport } from '~/utils/teamLogo'
import './home.css'

const LOGO_SIZE = 14

function Side({ sport, code }: { sport: HomeCard['sport'], code: string }) {
  return <>
    {isLogoSport(sport) && <span className="home-card__logo"><TeamLogo sport={sport} code={code} size={LOGO_SIZE} fallback="none" /></span>}
    {code}
  </>
}

function Segment({ sport, segment }: { sport: HomeCard['sport'], segment: HomeNextSegment }) {
  if ('text' in segment) return <>{segment.text}</>
  return <><Side sport={sport} code={segment.away} /> @ <Side sport={sport} code={segment.home} /></>
}

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
    {card.next && <p className="home-card__next">
      <span>{card.nextSegments.map((segment, index) => <Segment key={index} sport={card.sport} segment={segment} />)}</span>
    </p>}
    <div className="home-card__links">
      {card.links.map(link => <Link key={link.view} to={link.path}>{link.label}</Link>)}
      {card.tone === 'error' && <button type="button" onClick={onRetry}>Retry</button>}
    </div>
  </article>
}
