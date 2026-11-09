import { formDateText, formHistoryDate } from '~/utils/nflFormWindow'
import { type PlayerGameLog, playerFormAverages } from '~/utils/playerGameLog'
import './player-context.css'

interface Props {
  log: PlayerGameLog
  label: (market: string) => string
  valueText: (market: string, value: number | null) => string
  seasonStartMonth: number
  /** Why there is no graded per-player record yet. */
  recordNote: string
}

/** The three sections every player page ends with, in one order: averages, game log, model record. Gray reference only. */
export function PlayerContextSections({ log, label, valueText, seasonStartMonth, recordNote }: Props) {
  const averages = playerFormAverages(log)
  const now = new Date()
  return <>
    <h2 className="nfl-player-section-title">Recent averages <small>last {log.rows.length} games, last season included when needed</small></h2>
    <section className="nfl-player-card" aria-label="Recent averages">
      {averages.length === 0
        ? <p className="nfl-player-card__empty">No recent games loaded for this player.</p>
        : <dl className="player-form-averages">
          {averages.map(item => <div key={item.market}>
            <dt>{label(item.market)}</dt>
            <dd>{item.average.toFixed(1)}<small> avg · {item.games} g</small></dd>
          </div>)}
        </dl>}
    </section>

    <h2 className="nfl-player-section-title">Game log <small>from each market's recent games</small></h2>
    <section className="nfl-player-card" aria-label="Game log">
      {log.rows.length === 0
        ? <p className="nfl-player-card__empty">No recent games loaded for this player.</p>
        : <div className="nfl-player-table-wrap"><table className="nfl-player-table">
          <thead><tr><th>Date</th><th>Opp</th>{log.columns.map(market => <th key={market}>{label(market)}</th>)}</tr></thead>
          <tbody>{log.rows.map(row => <tr key={row.gameDate}>
            <td className="is-text">{formDateText(formHistoryDate(row.gameDate, now, seasonStartMonth)) ?? row.gameDate}</td>
            <td className="is-text is-dim">{row.opponent ?? '--'}</td>
            {row.values.map((value, index) => <td key={log.columns[index]}>{valueText(log.columns[index], value)}</td>)}
          </tr>)}</tbody>
        </table></div>}
    </section>

    <h2 className="nfl-player-section-title">Model record</h2>
    <section className="nfl-player-card" aria-label="Model record">
      <p className="nfl-player-card__empty">{recordNote}</p>
    </section>
  </>
}
