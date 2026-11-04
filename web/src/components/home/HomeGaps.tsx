import { Link } from 'react-router-dom'
import type { HomeGap } from '~/utils/homeSources'
import './home.css'

const SPORT_TAG: Record<HomeGap['sport'], string> = { nfl: 'NFL', nba: 'NBA' }

/** Gray reference rows, each sport in its own order; the player link covers its row. */
export function HomeGaps({ gaps }: { gaps: HomeGap[] }) {
  return <div className="home-panel home-gaps">
    {gaps.length === 0
      ? <p className="home-gaps__empty">No gap lines yet.</p>
      : <table>
        <thead><tr>
          <th>Player</th><th>Sport</th><th>Market</th><th className="is-num">Line</th><th className="is-num">Model</th><th className="is-num">Gap</th>
        </tr></thead>
        <tbody>
          {gaps.map(gap => <tr key={`${gap.sport}-${gap.key}`}>
            <td><Link to={gap.path}>{gap.playerName}</Link></td>
            <td><span className="home-tag">{SPORT_TAG[gap.sport]}</span></td>
            <td className="is-gray">{gap.market}</td>
            <td className="is-num is-mono">{gap.line}</td>
            <td className="is-num is-mono">{gap.model}</td>
            <td className="is-num is-mono is-gray">{gap.gap}</td>
          </tr>)}
        </tbody>
      </table>}
    <p className="home-panel__note">
      Gray means unvalidated reference. A row turns green only where that sport&apos;s own rule has validated the signal. Rows open that player&apos;s page.
    </p>
  </div>
}
