import { Link } from 'react-router-dom'
import type { HomeSport } from '~/hooks/useHomeData'
import type { HomeRecord } from '~/utils/homeRecords'
import { heroNext, nextStart, sportNoun } from '~/utils/home'
import { SPORTS, VIEW_LABELS, sportViews } from '~/utils/sportNav'
import './home.css'

function GapsPanel({ gaps }: { gaps: HomeSport['source']['gaps'] }) {
  return <div className="home-panel home-mini home-gaps">
    <table>
      <thead><tr><th>Largest gaps</th><th>Market</th><th className="is-num">Line</th><th className="is-num">Gap</th></tr></thead>
      <tbody>
        {gaps.map(gap => <tr key={gap.key}>
          <td>{gap.playerName}</td>
          <td className="is-gray">{gap.market}</td>
          <td className="is-num is-mono">{gap.line}</td>
          <td className="is-num is-mono is-gray">{gap.gap}</td>
        </tr>)}
      </tbody>
    </table>
    <p className="home-panel__note">Gray reference, not picks.</p>
  </div>
}

function NextGamesPanel({ games }: { games: HomeSport['source']['nextGames'] }) {
  return <div className="home-panel home-mini">
    <table>
      <thead><tr><th>Next up</th><th className="is-num">Starts (CT)</th></tr></thead>
      <tbody>
        {games.map(game => <tr key={game.key}><td>{game.title}</td><td className="is-num is-mono is-gray">{game.when}</td></tr>)}
      </tbody>
    </table>
  </div>
}

/** The lead sport: its counts, its largest gaps (or next games where it has none) and links to each of its views. */
export function HomeHero({ sport, record, now }: { sport: HomeSport, record: HomeRecord | undefined, now: number }) {
  const { sport: code } = sport.data
  const label = SPORTS.find(entry => entry.code === code)!.label
  const { source } = sport
  const start = nextStart(sport.data, now)
  const views = sportViews(code)
  return <div className="home-hero">
    <div>
      <h3>{label}{source.period && <> &middot; {source.period}</>}</h3>
      {start !== null && <p className="home-hero__sub">{heroNext(code, start, now)}</p>}
      <div className="home-hero__stats">
        <div>{source.gameCount}<small>{sportNoun(code, source.gameCount)}{code === 'tennis' ? ' priced' : ''}</small></div>
        {source.propLines !== null && <div>{source.propLines.toLocaleString()}<small>prop lines</small></div>}
        {record && <div className="home-hero__record">{record.label}<small>model record</small></div>}
      </div>
      <div className="home-hero__links">
        {views.map(({ view, path }, index) =>
          <Link key={view} to={path} className={index === 0 ? 'is-primary' : ''}>{VIEW_LABELS[view]}</Link>)}
      </div>
    </div>
    {source.gaps.length > 0
      ? <GapsPanel gaps={source.gaps} />
      : source.nextGames.length > 0 && <NextGamesPanel games={source.nextGames} />}
  </div>
}
