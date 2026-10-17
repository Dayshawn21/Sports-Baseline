import { Drawer, Switch } from 'antd'
import { useMemo, useState } from 'react'
import NflEvidencePanel from '~/components/NflEvidencePanel'
import { NflLineOnlyProps } from '~/components/nfl/NflLineOnlyProps'
import { NflPropCard } from '~/components/nfl/NflPropCard'
import { useIsMobile } from '~/hooks/useIsMobile'
import type { NflSlateGame } from '~/types/nfl'
import { hasKickedOff } from '~/utils/nflGame'
import { nflGameProps } from '~/utils/nflGameProps'
import { marketLabel } from '~/utils/nflLabels'
import type { NflBoardLine } from '~/utils/nflPropBoard'
import { NFL_POSITION_OPTIONS, type NflPositionFilter } from '~/utils/nflPositions'
import { NFL_PROP_PERIOD_OPTIONS, type NflPropPeriod } from '~/utils/nflPropPeriods'
import { groupNflPropRows } from '~/utils/nflPropRows'

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

/** The game's props as prop-board cards, ranked and scored by the week-wide board. */
export function NflGameProps({ games, game, now }: Props) {
  // One clock per visit, so the memoized board is not rebuilt on every render.
  const [mountedAt] = useState(() => new Date())
  const at = now ?? mountedAt
  const [period, setPeriod] = useState<NflPropPeriod>('full_game')
  const [position, setPosition] = useState<NflPositionFilter>('all')
  const [showAll, setShowAll] = useState(false)
  const [selected, setSelected] = useState<NflBoardLine | null>(null)
  const isMobile = useIsMobile()
  const categories = useMemo(() => nflGameProps(games, game.gameId, position, period, at), [games, game.gameId, position, period, at])
  const alternates = useMemo(() => new Map(groupNflPropRows(game.lines).map(item => [item.primary.lineId, item.alternates])), [game.lines])
  // Partial-game lines are never rateable, so hiding "other" there would always leave the view empty.
  const includeOther = showAll || period !== 'full_game'
  const visible = categories.filter(item => item.rateable.length > 0 || (includeOther && item.other.length > 0))
  const rateableCount = categories.reduce((total, item) => total + item.rateable.length, 0)
  const card = (row: NflBoardLine, rank: number | null, category: typeof categories[number]['category']) =>
    <NflPropCard key={row.lineId} row={row} rank={rank} category={category} selected={row.lineId === selected?.lineId} onOpen={setSelected} />
  return <section className="nfl-game-props" aria-label="Props for this game">
    <h2 className="nfl-game-section-title">Props <small>{rateableCount} rateable · ranks are from the week's prop board · edges stay gray until the ranking check adopts a slice</small></h2>
    <div className="nfl-game-props__toolbar">
      <Segment label="Period" options={NFL_PROP_PERIOD_OPTIONS} value={period} onChange={setPeriod} />
      <Segment label="Position" options={NFL_POSITION_OPTIONS} value={position} onChange={setPosition} />
      {period === 'full_game' && <label className="nfl-prop-toggle"><Switch size="small" checked={showAll} onChange={setShowAll} /><span>Show all lines</span></label>}
    </div>
    {hasKickedOff(game.startUtc, at) && <p className="nfl-game-note is-inline">Lines closed at kickoff. Ranks are as the board showed them just before.</p>}
    {game.lines.length === 0 && <div className="nfl-game-empty">No prop lines stored for this game yet.</div>}
    {game.lines.length > 0 && visible.length === 0 && <div className="nfl-game-empty">No modelled lines for this period and position. {period === 'full_game' && !showAll ? 'Turn on "Show all lines" for alternates and thin samples.' : ''}</div>}
    {visible.map(item => <section key={item.category.market} className="nfl-game-props__market" aria-label={`${marketLabel(item.category.market)} lines`}>
      <h3 className="nfl-game-label">{marketLabel(item.category.market)}</h3>
      <div className="nfl-prop-grid">
        {item.rateable.map(({ row, rank }) => card(row, rank, item.category))}
        {includeOther && item.other.map(row => card(row, null, item.category))}
      </div>
    </section>)}
    {/* Weekly stats are full-game totals, so partial-game line-only lines would show the wrong history. */}
    {period === 'full_game' && <NflLineOnlyProps gameId={game.gameId} position={position} />}
    <Drawer open={selected !== null} onClose={() => setSelected(null)} width={isMobile ? '100%' : 460} title={null} className="nfl-slate nfl-game nfl-game-drawer" destroyOnHidden>
      {selected && <NflEvidencePanel row={selected} game={game} alternates={alternates.get(selected.lineId) ?? []} showGameLink={false} />}
    </Drawer>
  </section>
}
