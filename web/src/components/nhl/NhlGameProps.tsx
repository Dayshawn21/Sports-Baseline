import { Link } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import GamePropFilters from '~/components/shared/GamePropFilters'
import LoadingState from '~/components/shared/LoadingState'
import { useGamePropFilters } from '~/hooks/useGamePropFilters'
import { useNhlLineOnlyProps } from '~/hooks/useNhl'
import { gamePlayerOptions, gamePropRowMatches } from '~/utils/propFilters'
import { nhlTimeLabel } from '~/utils/nhlGame'
import { nhlOddsTypeCounts, nhlPropListGroups, nhlSharedFetchedAt, type NhlPropListGroup, type NhlPropListRow } from '~/utils/nhlLineOnly'
import { nhlPlayerPath } from '~/utils/nhlPlayer'
import {
  NHL_PROBABILITY_CAPTION, NHL_WHOLE_LINE_NOTE, NHL_PROJECTION_CAPTION, nhlGapLabel, nhlPercentLabel, nhlProbabilityNote, nhlProjectionNote, nhlProjectionValue,
} from '~/utils/nhlProjection'

function alternates(row: NhlPropListRow): string {
  return row.rungs
    .filter(rung => rung.oddsType !== 'standard')
    .map(rung => `${rung.oddsTypeLabel} ${rung.label}${rung.gap === null ? '' : ` (${nhlGapLabel(rung.gap)})`}`)
    .join(' / ')
}

function MarketTable({ group, gameDate }: { group: NhlPropListGroup, gameDate: string }) {
  const covers = group.rows.some(row => row.coversProbability)
  const weakNote = nhlProbabilityNote(group.market)
  const wholeNote = group.rows.some(entry => entry.standardWholeLine) ? ` ${NHL_WHOLE_LINE_NOTE}` : ''
  const sharedFetchedAt = nhlSharedFetchedAt(group.rows)
  const perRowUpdated = sharedFetchedAt === null
  return <section className="nhl-prop-group" aria-labelledby={`nhl-props-${group.market}`}>
    <h3 id={`nhl-props-${group.market}`}>{group.label} <small>{group.rows.length} {group.rows.length === 1 ? 'player' : 'players'}</small></h3>
    {(covers || !perRowUpdated) && <p className="nhl-prop-caption">
      {covers && <>{NHL_PROBABILITY_CAPTION}. Shown for the standard line only.{wholeNote}{weakNote && ` ${weakNote}`} </>}
      {!perRowUpdated && <>Updated <time dateTime={sharedFetchedAt}>{nhlTimeLabel(sharedFetchedAt, true)}</time>.</>}
    </p>}
    <table className="nhl-prop-table" aria-label={`${group.label} lines`}>
      <thead><tr>
        <th scope="col" className="nhl-prop-col-player">Player</th>
        <th scope="col" className="nhl-prop-col-line">Standard</th>
        <th scope="col" className="nhl-prop-col-line">Proj</th>
        <th scope="col" className="nhl-prop-col-gap">Gap</th>
        {covers && <th scope="col" className="nhl-prop-col-pover">P(over)</th>}
        <th scope="col" className="nhl-prop-alt">Other lines</th>
        {perRowUpdated && <th scope="col" className="nhl-prop-updated">Updated (CT)</th>}
      </tr></thead>
      <tbody>{group.rows.map(row => {
        const others = alternates(row)
        return <tr key={row.key}>
          <td>
            <strong><Link className="nhl-prop-link" to={nhlPlayerPath(row.playerId, { date: gameDate, market: row.market })}>{row.playerName}</Link></strong>
            <small>{row.team ?? '--'}{row.position ? ` / ${row.position}` : ''}</small>
            {others && <small className="nhl-prop-alt-mobile">Other lines: {others}</small>}
            {perRowUpdated && <time className="nhl-prop-updated-mobile" dateTime={row.fetchedAt}>{nhlTimeLabel(row.fetchedAt, true)}</time>}
          </td>
          <td className="nhl-prop-line">{row.standard ?? '--'}</td>
          <td className="nhl-prop-line">{nhlProjectionValue(row.projection)}{nhlProjectionNote(row.projection) && <small>{nhlProjectionNote(row.projection)}</small>}</td>
          <td className="nhl-prop-line">{nhlGapLabel(row.standardGap)}</td>
          {covers && <td className="nhl-prop-line">{nhlPercentLabel(row.standardPOver)}{row.standardProbabilityNote && <small>{row.standardProbabilityNote}</small>}</td>}
          <td className="nhl-prop-alt">{others || '--'}</td>
          {perRowUpdated && <td className="nhl-prop-updated"><time dateTime={row.fetchedAt}>{nhlTimeLabel(row.fetchedAt, true)}</time></td>}
        </tr>
      })}</tbody>
    </table>
  </section>
}

/** The game page's player props: one row per player per market, each opening that player's page on this game's date. */
export function NhlGameProps({ game }: { game: { gameId: number, gameDate: string, awayTeam: string, homeTeam: string } }) {
  const { gameId, gameDate } = game
  const query = useNhlLineOnlyProps(gameId)
  const { filter, onPlayers, onTeam } = useGamePropFilters(game)
  if (query.isLoading) return <LoadingState message="Loading NHL player props..." />
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const lines = query.data.lines
  const groups = nhlPropListGroups(lines)
  const playerNames = gamePlayerOptions(lines, game, filter)
  const shown = groups.map(group => ({ ...group, rows: group.rows.filter(row => gamePropRowMatches(row, game, filter)) })).filter(group => group.rows.length > 0)
  return <section className="nhl-props" aria-label="Player props">
    <div className="nhl-props-heading"><h2>Player props</h2><p>PrizePicks full-game lines. {NHL_PROJECTION_CAPTION}. Open a player for the form chart and every line.</p></div>
    <dl className="nhl-props-counts" aria-label="Stored prop line counts">
      <div><dt>Total lines</dt><dd>{lines.length}</dd></div>
      {nhlOddsTypeCounts(lines).map(entry => <div key={entry.oddsType}><dt>{entry.label}</dt><dd>{entry.count}</dd></div>)}
    </dl>
    {groups.length > 0 && <GamePropFilters game={game} playerNames={playerNames} filter={filter} onPlayers={onPlayers} onTeam={onTeam} />}
    {groups.length === 0
      ? <p className="nfl-game-empty">No linked full-game PrizePicks lines are stored for this game.</p>
      : shown.length === 0 ? <p className="nfl-game-empty">No props match these filters.</p>
        : shown.map(group => <MarketTable key={group.market} group={group} gameDate={gameDate} />)}
  </section>
}
