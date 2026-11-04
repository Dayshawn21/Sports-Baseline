import { Link } from 'react-router-dom'
import { nhlPuckDropLabel } from '~/utils/nhlGame'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlBoardGameStatus, type NhlBoardMarket } from '~/utils/nhlPropBoard'
import { nhlPlayerPath } from '~/utils/nhlPlayer'

function alternates(rungs: NhlBoardMarket['rows'][number]['row']['rungs']): string {
  return rungs
    .filter(rung => rung.oddsType !== 'standard')
    .map(rung => `${rung.oddsTypeLabel} ${rung.label}`)
    .join(' / ')
}

/** One market's rows, each opening that player's page on this date and market; values stay gray and unranked. */
export default function NhlPropBoardMarket({ group, date }: { group: NhlBoardMarket, date: string }) {
  const label = nhlMarketLabel(group.market)
  const now = new Date()
  if (group.rows.length === 0) return <p className="nfl-empty">No {label.toLowerCase()} lines on this date.</p>
  return <section className="nhl-prop-board__rows" aria-label={`${label} lines`}>
    <table className="nhl-prop-board__table">
      <thead><tr>
        <th scope="col">Player</th><th scope="col">Game</th><th scope="col">Puck drop</th>
        <th scope="col">Standard</th><th scope="col">Other lines</th>
      </tr></thead>
      <tbody>{group.rows.map(({ key, game, row }) => {
        const status = nhlBoardGameStatus(game, now)
        return <tr key={key}>
          <td>
            <Link className="nhl-prop-board__player" to={nhlPlayerPath(row.playerId, { date, market: group.market })}>{row.playerName}</Link>
            <small>{row.team ?? '--'}{row.position ? ` / ${row.position}` : ''}</small>
          </td>
          <td><Link className="nhl-prop-board__game" to={`/nhl/game/${game.gameId}`}>{game.awayTeam} @ {game.homeTeam}</Link></td>
          <td>{nhlPuckDropLabel(game.startUtc)}{status && <small>{status}</small>}</td>
          <td className="nhl-prop-board__line">{row.standard ?? '--'}</td>
          <td>{alternates(row.rungs) || '--'}</td>
        </tr>
      })}</tbody>
    </table>
  </section>
}
