import { Switch } from 'antd'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflLineOnlyProps } from '~/components/nfl/NflLineOnlyProps'
import { NflPropTable } from '~/components/nfl/NflPropTable'
import { NflSlateDigest } from '~/components/nfl/NflSlateDigest'
import GamePropFilters from '~/components/shared/GamePropFilters'
import { useGamePropFilters } from '~/hooks/useGamePropFilters'
import { useNflLineOnlyProps } from '~/hooks/useNfl'
import { useRestoreOpenedRow } from '~/hooks/useRestoreOpenedRow'
import type { NflSeasonWeek, NflSlateGame } from '~/types/nfl'
import { hasKickedOff } from '~/utils/nflGame'
import { filterNflGameProps, nflGamePlayerOptions, nflGameProps } from '~/utils/nflGameProps'
import { marketLabel } from '~/utils/nflLabels'
import { lineOnlyGroups } from '~/utils/nflLineOnly'
import { nflPlayerMarketLink } from '~/utils/nflPlayer'
import { NFL_POSITION_OPTIONS } from '~/utils/nflPositions'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { slateDigest } from '~/utils/nflSlate'
import { isTargetsReference } from '~/utils/nflTargets'
import { gameViewSearch, parseGameView } from '~/utils/nflViewParams'
import { gamePropRowMatches, withPropListFilters } from '~/utils/propFilters'

function Segment<T extends string>({ label, options, value, onChange }: { label: string, options: Array<{ label: string, value: T }>, value: T, onChange: (value: T) => void }) {
  return <div className="nfl-prop-seg" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" className={value === option.value ? 'is-selected' : ''} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}

interface Props {
  games: NflSlateGame[]
  game: NflSlateGame
  /** The game's own week, carried into every player link. */
  week: NflSeasonWeek
  now?: Date
}

/** The game's props as prop-board rows, scored against the week-wide board. */
export function NflGameProps({ games, game, week, now }: Props) {
  // One clock per visit, so the memoized board is not rebuilt on every render.
  const [mountedAt] = useState(() => new Date())
  const at = now ?? mountedAt
  // In the URL so Back from a player page returns to the same view.
  const [params, setParams] = useSearchParams()
  const { position, showAll } = parseGameView(params)
  const { filter, filtering, onPlayers, onTeam } = useGamePropFilters(game)
  const setView = (patch: Partial<ReturnType<typeof parseGameView>>) => setParams(withPropListFilters(gameViewSearch({ position, showAll, ...patch }), { player: filter.players, team: filter.team }), { replace: true })
  useRestoreOpenedRow(true)
  const categories = useMemo(() => nflGameProps(games, game.gameId, position, 'full_game', at), [games, game.gameId, position, at])
  const shown = filterNflGameProps(categories, filter)
  const lineOnly = useNflLineOnlyProps(game.gameId)
  const otherRows = lineOnly.data ? lineOnlyGroups(lineOnly.data.lines, position).flatMap(group => group.rows) : []
  const playerNames = nflGamePlayerOptions(categories, otherRows.filter(row => gamePropRowMatches(row, game, { ...filter, players: [] })).map(row => row.playerName), filter, showAll)
  // The week-wide board (its reference lines set the gap share, so boxes match the slate's numbers),
  // narrowed to this game and left unfiltered so a box shows whatever position is chosen.
  const board = useMemo(() => buildNflPropBoard(games, 'all', at)
    .map(item => ({ ...item, rateable: item.rateable.filter(row => row.gameId === game.gameId) })), [games, game.gameId, at])
  const digest = useMemo(() => slateDigest(board), [board])
  const visible = shown.filter(item => item.rateable.length > 0 || (showAll && item.other.length > 0))
  const rateableCount = categories.filter(item => !isTargetsReference(item.category.market)).reduce((total, item) => total + item.rateable.length, 0)
  return <section className="nfl-game-props" aria-label="Props for this game">
    <NflSlateDigest items={digest} scope="this game" linkFor={item => nflPlayerMarketLink(item.playerId, item.marketKey, week)} />
    <h2 className="nfl-game-section-title">Props <small>{rateableCount} comparable lines</small></h2>
    <p className="nfl-game-props__intro">Compare projections with full-game lines. Gray gaps are research comparisons, not recommendations.</p>
    <details className="nfl-game-props__help">
      <summary>How to read these comparisons</summary>
      <p>Over and Under show which side of the line the projection falls on. Ready, Watch and Review describe data quality, not betting confidence. Rows follow kickoff, then player name, and are not ranked. <Link to="/nfl/model">View model validation</Link>.</p>
    </details>
    <GamePropFilters game={game} playerNames={playerNames} filter={filter} onPlayers={onPlayers} onTeam={onTeam} />
    <div className="nfl-game-props__toolbar">
      <span className="nfl-game-props__period">Full game</span>
      <Segment label="Position" options={NFL_POSITION_OPTIONS} value={position} onChange={value => setView({ position: value })} />
      <label className="nfl-prop-toggle"><Switch size="small" checked={showAll} onChange={value => setView({ showAll: value })} /><span>Include alternate and thin-sample lines</span></label>
    </div>
    {hasKickedOff(game.startUtc, at) && <p className="nfl-game-note is-inline">Lines closed at kickoff. Rows are as the board showed them just before.</p>}
    {game.lines.length === 0 && <div className="nfl-game-empty">No prop lines stored for this game yet.</div>}
    {game.lines.length > 0 && visible.length === 0 && <div className="nfl-game-empty">{filtering ? 'No comparable lines match these filters.' : 'No comparable full-game lines for this position.'} {!showAll ? 'Include alternate and thin-sample lines, or choose another position.' : 'Choose another position or check the other markets below.'}</div>}
    {visible.map(item => <section key={item.category.market} className="nfl-game-props__market prop-table-panel" aria-label={`${marketLabel(item.category.market)} lines`}>
      <h3 className="nfl-game-label">{marketLabel(item.category.market)}</h3>
      <NflPropTable category={item.category} now={at.getTime()} inGame week={week}
        rateable={item.rateable} other={showAll ? item.other : []} />
    </section>)}
    <NflLineOnlyProps game={game} position={position} week={week} filter={filter} />
  </section>
}
