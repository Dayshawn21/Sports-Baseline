import { Switch } from 'antd'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflLineOnlyProps } from '~/components/nfl/NflLineOnlyProps'
import { NflPropTable } from '~/components/nfl/NflPropTable'
import { NflSlateDigest } from '~/components/nfl/NflSlateDigest'
import { useRestoreOpenedRow } from '~/hooks/useRestoreOpenedRow'
import type { NflSlateGame } from '~/types/nfl'
import { hasKickedOff } from '~/utils/nflGame'
import { nflGameProps } from '~/utils/nflGameProps'
import { marketLabel } from '~/utils/nflLabels'
import { nflPlayerMarketLink } from '~/utils/nflPlayer'
import { NFL_POSITION_OPTIONS } from '~/utils/nflPositions'
import { buildNflPropBoard } from '~/utils/nflPropBoard'
import { slateDigest } from '~/utils/nflSlate'
import { isTargetsReference } from '~/utils/nflTargets'
import { gameViewSearch, parseGameView } from '~/utils/nflViewParams'

function Segment<T extends string>({ label, options, value, onChange }: { label: string, options: Array<{ label: string, value: T }>, value: T, onChange: (value: T) => void }) {
  return <div className="nfl-prop-seg" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" className={value === option.value ? 'is-selected' : ''} aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}

interface Props {
  games: NflSlateGame[]
  game: NflSlateGame
  now?: Date
}

/** The game's props as prop-board rows, ranked and scored by the week-wide board. */
export function NflGameProps({ games, game, now }: Props) {
  // One clock per visit, so the memoized board is not rebuilt on every render.
  const [mountedAt] = useState(() => new Date())
  const at = now ?? mountedAt
  // In the URL so Back from a player page returns to the same view.
  const [params, setParams] = useSearchParams()
  const { position, showAll } = parseGameView(params)
  const setView = (patch: Partial<ReturnType<typeof parseGameView>>) => setParams(gameViewSearch({ position, showAll, ...patch }), { replace: true })
  useRestoreOpenedRow(true)
  const categories = useMemo(() => nflGameProps(games, game.gameId, position, 'full_game', at), [games, game.gameId, position, at])
  // The week-wide board (its reference lines set the gap share, so boxes match the slate's numbers),
  // narrowed to this game and left unfiltered so a box shows whatever position is chosen.
  const board = useMemo(() => buildNflPropBoard(games, 'all', at)
    .map(item => ({ ...item, rateable: item.rateable.filter(row => row.gameId === game.gameId) })), [games, game.gameId, at])
  const digest = useMemo(() => slateDigest(board), [board])
  const visible = categories.filter(item => item.rateable.length > 0 || (showAll && item.other.length > 0))
  const rateableCount = categories.filter(item => !isTargetsReference(item.category.market)).reduce((total, item) => total + item.rateable.length, 0)
  return <section className="nfl-game-props" aria-label="Props for this game">
    <NflSlateDigest items={digest} scope="this game" linkFor={item => nflPlayerMarketLink(item.playerId, item.marketKey)} />
    <h2 className="nfl-game-section-title">Props <small>{rateableCount} comparable lines · ranks from this week's prop board</small></h2>
    <p className="nfl-game-props__intro">Compare projections with full-game lines. Gray gaps are research comparisons, not recommendations.</p>
    <details className="nfl-game-props__help">
      <summary>How to read these comparisons</summary>
      <p>Over and Under show which side of the line the projection falls on. Ready, Watch and Review describe data quality, not betting confidence. A rank shows a line's place on the weekly prop board; it does not make it a recommended bet. <Link to="/nfl/model">View model validation</Link>.</p>
    </details>
    <div className="nfl-game-props__toolbar">
      <span className="nfl-game-props__period">Full game</span>
      <Segment label="Position" options={NFL_POSITION_OPTIONS} value={position} onChange={value => setView({ position: value })} />
      <label className="nfl-prop-toggle"><Switch size="small" checked={showAll} onChange={value => setView({ showAll: value })} /><span>Include alternate and thin-sample lines</span></label>
    </div>
    {hasKickedOff(game.startUtc, at) && <p className="nfl-game-note is-inline">Lines closed at kickoff. Ranks are as the board showed them just before.</p>}
    {game.lines.length === 0 && <div className="nfl-game-empty">No prop lines stored for this game yet.</div>}
    {game.lines.length > 0 && visible.length === 0 && <div className="nfl-game-empty">No comparable full-game lines for this position. {!showAll ? 'Include alternate and thin-sample lines, or choose another position.' : 'Choose another position or check the other markets below.'}</div>}
    {visible.map(item => <section key={item.category.market} className="nfl-game-props__market prop-table-panel" aria-label={`${marketLabel(item.category.market)} lines`}>
      <h3 className="nfl-game-label">{marketLabel(item.category.market)}</h3>
      <NflPropTable category={item.category} now={at.getTime()} inGame
        rateable={item.rateable} other={showAll ? item.other.map(row => ({ row, rank: null })) : []} />
    </section>)}
    <NflLineOnlyProps gameId={game.gameId} position={position} />
  </section>
}
