import type { CSSProperties } from 'react'
import type { NflPlayerDetail } from '~/types/nfl'
import { marketLabel } from '~/utils/nflLabels'
import { FOCUS_LABELS } from '~/utils/nflPlayer'

const MISSING = '--'

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

/** Over hits against each stored line, never colored: a few games per market is anecdote, not a verdict. */
function PastLines({ player }: { player: NflPlayerDetail }) {
  return <section className="nfl-player-card" aria-label="Past PrizePicks lines">
    <div className="nfl-player-card__head">
      <span className="nfl-player-label">Past PrizePicks lines</span>
      <span className="nfl-player-muted">Standard, full game, {player.season}</span>
    </div>
    {player.pastLines.length === 0
      ? <p className="nfl-player-card__empty">No stored lines have settled yet.</p>
      : <div className="nfl-player-card__body">
        {player.pastLines.map(count => <div key={count.market} className="nfl-player-rate">
          <span>{marketLabel(count.market)}</span>
          <span className="nfl-player-meter" role="img" aria-label={`${count.overs} overs of ${count.decided}, break-even ${pct(player.breakEven)}`}
            style={{ '--v': `${(count.overs / count.decided) * 100}%`, '--be': `${player.breakEven * 100}%` } as CSSProperties}>
            <i /><b />
          </span>
          <b>{count.overs} of {count.decided}</b>
        </div>)}
        <p className="nfl-player-note">Overs hit against each stored line; the white tick is the {pct(player.breakEven)} Power break-even. A handful of games is anecdote, so nothing here is colored. The model&apos;s graded record belongs on the Model view (33d).</p>
      </div>}
  </section>
}

function perGame(value: number | null): string {
  return value === null ? MISSING : value.toFixed(1)
}

function Splits({ player, focus, volume }: { player: NflPlayerDetail, focus: string, volume: string }) {
  const window = player.splits[0]?.games ?? 0
  return <section className="nfl-player-card" aria-label="Record splits">
    <div className="nfl-player-card__head">
      <span className="nfl-player-label">Record splits</span>
      <span className="nfl-player-muted">Last {window} games</span>
    </div>
    <div className="nfl-player-table-wrap"><table className="nfl-player-table">
      <thead><tr><th>Split</th><th>G</th><th>{focus}</th><th>{volume}</th><th>Snaps</th></tr></thead>
      <tbody>{player.splits.map(split => <tr key={split.label}>
        <td className="is-text">{split.label}</td><td>{split.games}</td>
        <td>{perGame(split.focusPerGame)}</td><td>{perGame(split.volumePerGame)}</td>
        <td>{split.snapShare === null ? MISSING : `${Math.round(split.snapShare * 100)}%`}</td>
      </tr>)}</tbody>
    </table></div>
  </section>
}

export function NflPlayerRecord({ player }: { player: NflPlayerDetail }) {
  const labels = player.focusMarket ? FOCUS_LABELS[player.focusMarket] : undefined
  return <div className="nfl-player-grid is-record">
    <PastLines player={player} />
    {labels && player.splits.length > 0 && <Splits player={player} focus={labels.focus.replace(' / g', '')} volume={labels.volume.replace(' / g', '')} />}
  </div>
}

/** Data freshness and provider-name overrides; aliases are omitted when there are none. */
export function NflPlayerFooter({ player }: { player: NflPlayerDetail }) {
  const through = player.statsThrough ? `NFLverse weekly stats and snaps through ${player.statsThrough.season} W${player.statsThrough.week}.` : 'No weekly stats loaded yet.'
  return <p className="nfl-player-note nfl-player-footer">
    {through} Roster, depth and injuries as of week {player.week}.
    {player.aliases.length > 0 && <> Aliases: {player.aliases.map(alias => `"${alias}"`).join(', ')}.</>}
  </p>
}
