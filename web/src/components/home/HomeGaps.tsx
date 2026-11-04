import { Link } from 'react-router-dom'
import type { GapTabKey, GapsBody, GapsFooter, HomeGapTab } from '~/utils/home'
import type { HomeGap, HomeNextGame } from '~/utils/homeSources'
import './home.css'

const SPORT_TAG: Record<HomeGap['sport'], string> = { nfl: 'NFL', nba: 'NBA' }

interface Props {
  tabs: HomeGapTab[]
  selected: GapTabKey
  hrefFor: (key: GapTabKey) => string
  body: GapsBody
}

function GapRows({ rows, showSport }: { rows: HomeGap[], showSport: boolean }) {
  return <table>
    <thead><tr>
      <th>Player</th>
      {showSport && <th>Sport</th>}
      <th className="col-market">Market</th><th>Time</th><th className="is-num col-line">Line</th><th className="is-num col-model">Model</th><th className="is-num">Gap</th>
    </tr></thead>
    <tbody>
      {rows.map(gap => <tr key={`${gap.sport}-${gap.key}`}>
        <td><Link to={gap.path}>{gap.playerName}</Link></td>
        {showSport && <td><span className="home-tag">{SPORT_TAG[gap.sport]}</span></td>}
        <td className="is-gray col-market">{gap.market}</td>
        <td className="is-gray is-nowrap">{gap.when}</td>
        <td className="is-num is-mono col-line">{gap.line}</td>
        <td className="is-num is-mono col-model">{gap.model}</td>
        <td className="is-num is-mono is-gray">{gap.gap}</td>
      </tr>)}
    </tbody>
  </table>
}

function NextGames({ games }: { games: HomeNextGame[] }) {
  return <table>
    <thead><tr><th>Game</th><th>Time</th></tr></thead>
    <tbody>
      {games.map(game => <tr key={game.key}>
        <td>{game.title}</td>
        <td className="is-gray is-nowrap">{game.when}</td>
      </tr>)}
    </tbody>
  </table>
}

function Footer({ footer }: { footer: GapsFooter }) {
  return <p className="home-gaps__footer"><Link to={footer.path}>{footer.label}</Link></p>
}

function Body({ body, selected }: { body: GapsBody, selected: GapTabKey }) {
  if (body.kind === 'loading') return <p className="home-gaps__empty">Loading</p>
  if (body.kind === 'error') return <p className="home-gaps__empty">{body.text}</p>
  if (body.kind === 'games') {
    return <>
      <p className="home-gaps__intro">{body.intro}</p>
      {body.games.length === 0 ? <p className="home-gaps__empty">{body.empty}</p> : <NextGames games={body.games} />}
      <Footer footer={body.footer} />
    </>
  }
  return <>
    {body.rows.length === 0 ? <p className="home-gaps__empty">{body.empty}</p> : <GapRows rows={body.rows} showSport={selected === 'all'} />}
    {selected === 'all' && <p className="home-gaps__footer">NHL and Tennis have no gap rows; see their tabs for next games.</p>}
    {body.footer && <Footer footer={body.footer} />}
  </>
}

/** Gray reference rows, each sport in its own order; the player link covers its row. */
export function HomeGaps({ tabs, selected, hrefFor, body }: Props) {
  return <div className="home-panel home-gaps">
    <nav className="home-gaps__tabs" aria-label="Choose a sport">
      {tabs.map(tab => <Link key={tab.key} to={hrefFor(tab.key)} replace aria-current={tab.key === selected ? 'true' : undefined}>{tab.text}</Link>)}
    </nav>
    <Body body={body} selected={selected} />
    <p className="home-panel__note">
      Gray means unvalidated reference. A row turns green only where that sport&apos;s own rule has validated the signal. Rows open that player&apos;s page.
    </p>
  </div>
}
