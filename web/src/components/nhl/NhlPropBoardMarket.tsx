import { Link } from 'react-router-dom'
import { AltLinesChip } from '~/components/shared/AltLinesChip'
import { ProbabilityRing } from '~/components/shared/ProbabilityRing'
import { nhlPuckDropLabel } from '~/utils/nhlGame'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlBoardGameStatus, type NhlBoardMarket } from '~/utils/nhlPropBoard'
import { nhlPlayerPath } from '~/utils/nhlPlayer'
import { FROM_BOARD } from '~/utils/playerPage'
import { REFERENCE, probabilityRing } from '~/utils/propRowVisuals'
import { nhlAlternateLabels, nhlGapLabel, nhlPercentLabel, nhlProbabilityCaption, nhlProjectionNote, nhlProjectionValue } from '~/utils/nhlProjection'

/** One market's rows, each opening that player's page on this date and market as a board arrival; values stay gray and unranked. */
export default function NhlPropBoardMarket({ group, date }: { group: NhlBoardMarket, date: string }) {
  const label = nhlMarketLabel(group.market)
  const now = new Date()
  const caption = nhlProbabilityCaption(group.market, group.rows.map(entry => entry.row))
  const covers = caption !== null
  if (group.rows.length === 0) return <p className="nfl-empty">No {label.toLowerCase()} lines on this date.</p>
  return <section className="nhl-prop-board__rows" aria-label={`${label} lines`}>
    {covers && <p className="nhl-prop-board__caption">{caption}</p>}
    <table className="nhl-prop-board__table">
      <thead><tr>
        <th scope="col">Player</th><th scope="col">Game</th><th scope="col">Puck drop</th>
        <th scope="col">Standard</th><th scope="col">Proj</th><th scope="col">Gap</th>{covers && <th scope="col">P(over)</th>}<th scope="col">Other lines</th>
      </tr></thead>
      <tbody>{group.rows.map(({ key, game, row }) => {
        const status = nhlBoardGameStatus(game, now)
        const others = nhlAlternateLabels(row.rungs)
        return <tr key={key}>
          <td>
            <Link className="nhl-prop-board__player" to={nhlPlayerPath(row.playerId, { date, market: group.market })} state={FROM_BOARD}>{row.playerName}</Link>
            <small>{row.team ?? '--'}{row.position ? ` / ${row.position}` : ''}</small>
          </td>
          <td><Link className="nhl-prop-board__game" to={`/nhl/game/${game.gameId}`}>{game.awayTeam} @ {game.homeTeam}</Link></td>
          <td>{nhlPuckDropLabel(game.startUtc)}{status && <small>{status}</small>}</td>
          <td className="nhl-prop-board__line">{row.standard ?? '--'}</td>
          <td className="nhl-prop-board__line">{nhlProjectionValue(row.projection)}{nhlProjectionNote(row.projection) && <small>{nhlProjectionNote(row.projection)}</small>}</td>
          <td className="nhl-prop-board__line">{nhlGapLabel(row.standardGap)}</td>
          {covers && <td className="nhl-prop-board__line"><ProbabilityRing ring={probabilityRing(row.standardPOver === null ? null : row.standardPOver * 100, REFERENCE)} />{nhlPercentLabel(row.standardPOver)}{row.standardProbabilityNote && <small>{row.standardProbabilityNote}</small>}</td>}
          <td>{others.length ? <AltLinesChip labels={others} context={label} /> : '--'}</td>
        </tr>
      })}</tbody>
    </table>
  </section>
}
