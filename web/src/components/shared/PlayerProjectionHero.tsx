import type { PlayerProjectionHero as Hero } from '~/utils/playerProjection'
import './player-projection.css'

/** The top of a player's market panel: the projected number against the main line, or why there is none. Always gray. */
export function PlayerProjectionHero({ hero }: { hero: Hero }) {
  return <section className="player-projection" aria-label={hero.label}>
    <span className="player-projection__label">{hero.label}</span>
    <div className="player-projection__row">
      <strong className={hero.value === null ? 'is-none' : undefined}>{hero.value ?? 'No projection'}</strong>
      <dl className="player-projection__facts">
        {hero.facts.map(fact => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}
      </dl>
    </div>
    {hero.delta && <p className="player-projection__delta">{hero.delta}</p>}
    {hero.reason && <p className="player-projection__reason">{hero.reason}</p>}
  </section>
}
