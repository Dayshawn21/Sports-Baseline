import { Link } from 'react-router-dom'
import type { GapKind, GapTabKey, GapsBody, GapsFooter, HomeGapTab } from '~/utils/home'
import type { HomeGap, HomeMoneyline, HomeNextGame } from '~/utils/homeSources'
import './home.css'

const SPORT_TAG: Record<HomeGap['sport'], string> = { nfl: 'NFL', nba: 'NBA', tennis: 'Tennis' }
const KINDS: { key: GapKind, label: string }[] = [{ key: 'props', label: 'Props' }, { key: 'ml', label: 'Moneyline' }]

interface Props {
  tabs: HomeGapTab[]
  selected: GapTabKey
  kind: GapKind
  tabHref: (key: GapTabKey) => string
  kindHref: (kind: GapKind) => string
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
        <td className="is-num is-mono is-gray">{gap.gap}{gap.share && <span className="home-gaps__share"> · {gap.share}</span>}</td>
      </tr>)}
    </tbody>
  </table>
}

function MoneylineRows({ rows, showSport }: { rows: HomeMoneyline[], showSport: boolean }) {
  return <table>
    <thead><tr>
      <th>Side</th><th className="col-game">Game</th>
      {showSport && <th>Sport</th>}
      <th>Time</th><th className="is-num col-market">Market</th><th className="is-num col-model">Model</th><th className="is-num">Gap</th>
    </tr></thead>
    <tbody>
      {rows.map(row => <tr key={`${row.sport}-${row.key}`}>
        <td><Link to={row.path}>{row.side}</Link></td>
        <td className="is-gray col-game">{row.matchup}</td>
        {showSport && <td><span className="home-tag">{SPORT_TAG[row.sport]}</span></td>}
        <td className="is-gray is-nowrap">{row.when}</td>
        <td className="is-num is-mono col-market">{row.market}</td>
        <td className="is-num is-mono col-model">{row.model}</td>
        <td className="is-num is-mono is-gray">{row.gap}</td>
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
  if (body.kind === 'moneyline') {
    return <>
      {body.rows.length === 0 ? <p className="home-gaps__empty">{body.empty}</p> : <MoneylineRows rows={body.rows} showSport={selected === 'all'} />}
      <p className="home-gaps__footer">{body.note}</p>
      {body.footer && <Footer footer={body.footer} />}
    </>
  }
  return <>
    {body.rows.length === 0 ? <p className="home-gaps__empty">{body.empty}</p> : <GapRows rows={body.rows} showSport={selected === 'all'} />}
    {body.rows.length > 0 && <p className="home-gaps__footer">
      Gap is model minus line in the stat&apos;s units. Each sport orders its rows by the percentage beside it; NFL lists lines with 8+ games of history first.
    </p>}
    {selected === 'all' && <p className="home-gaps__footer">NHL props have no projection, so it has no gap rows; see its tab for next games.</p>}
    {body.footer && <Footer footer={body.footer} />}
  </>
}

/** Gray reference rows, each sport in its own order; the player link covers its row. */
export function HomeGaps({ tabs, selected, kind, tabHref, kindHref, body }: Props) {
  return <div className="home-panel home-gaps">
    <nav className="home-gaps__kinds" aria-label="Choose props or moneyline">
      {KINDS.map(entry => <Link key={entry.key} to={kindHref(entry.key)} replace aria-current={entry.key === kind ? 'true' : undefined}>{entry.label}</Link>)}
    </nav>
    <nav className="home-gaps__tabs" aria-label="Choose a sport">
      {tabs.map(tab => <Link key={tab.key} to={tabHref(tab.key)} replace aria-current={tab.key === selected ? 'true' : undefined}>{tab.text}</Link>)}
    </nav>
    <Body body={body} selected={selected} />
    <p className="home-panel__note">
      Gray means unvalidated reference. A row turns green only where that sport&apos;s own rule has validated the signal. Rows open the player or game page.
    </p>
  </div>
}
