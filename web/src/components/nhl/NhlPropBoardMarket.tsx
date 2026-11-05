import { Link } from 'react-router-dom'
import { nhlPuckDropLabel } from '~/utils/nhlGame'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlBoardGameStatus, type NhlBoardMarket } from '~/utils/nhlPropBoard'
import { nhlPlayerPath } from '~/utils/nhlPlayer'
import {
  NHL_PROBABILITY_CAPTION, nhlGapLabel, nhlPercentLabel, nhlProbabilityNote, nhlProjectionNote, nhlProjectionValue,
} from '~/utils/nhlProjection'

function alternates(rungs: NhlBoardMarket['rows'][number]['row']['rungs']): string {
  return rungs
    .filter(rung => rung.oddsType !== 'standard')
    .map(rung => `${rung.oddsTypeLabel} ${rung.label}${rung.gap === null ? '' : ` (${nhlGapLabel(rung.gap)})`}`)
    .join(' / ')
}

/** One market's rows, each opening that player's page on this date and market; values stay gray and unranked. */
export default function NhlPropBoardMarket({ group, date }: { group: NhlBoardMarket, date: string }) {
  const label = nhlMarketLabel(group.market)
  const now = new Date()
  const covers = group.rows.some(entry => entry.row.coversProbability)
  const weakNote = nhlProbabilityNote(group.market)
  if (group.rows.length === 0) return <p className="nfl-empty">No {label.toLowerCase()} lines on this date.</p>
  return <section className="nhl-prop-board__rows" aria-label={`${label} lines`}>
    {covers && <p className="nhl-prop-board__caption">{NHL_PROBABILITY_CAPTION}. Shown for the standard line only.{weakNote && ` ${weakNote}`}</p>}
    <table className="nhl-prop-board__table">
      <thead><tr>
        <th scope="col">Player</th><th scope="col">Game</th><th scope="col">Puck drop</th>
        <th scope="col">Standard</th><th scope="col">Proj</th><th scope="col">Gap</th>{covers && <th scope="col">P(over)</th>}<th scope="col">Other lines</th>
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
          <td className="nhl-prop-board__line">{nhlProjectionValue(row.projection)}{nhlProjectionNote(row.projection) && <small>{nhlProjectionNote(row.projection)}</small>}</td>
          <td className="nhl-prop-board__line">{nhlGapLabel(row.standardGap)}</td>
          {covers && <td className="nhl-prop-board__line">{nhlPercentLabel(row.standardPOver)}{row.standardProbabilityNote && <small>{row.standardProbabilityNote}</small>}</td>}
          <td>{alternates(row.rungs) || '--'}</td>
        </tr>
      })}</tbody>
    </table>
  </section>
}
