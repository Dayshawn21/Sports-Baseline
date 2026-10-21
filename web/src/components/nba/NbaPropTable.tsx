import type { MouseEvent, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { MiniBars } from '~/components/shared/MiniBars'
import { nbaMarketLabel, nbaRecentValueLabel, type NbaLineOnlyRow } from '~/utils/nbaLineOnly'
import { lineOnlyBars, mainRung } from '~/utils/nflLineOnly'
import type { NbaPropCard } from '~/utils/nbaProps'
import { nbaBoardGameLabels, type NbaBoardGameContext, type NbaBoardRow } from '~/utils/nbaPropBoard'
import '~/components/shared/prop-table.css'
import './nba-prop-table.css'

interface PlayerProps {
  playerName: string
  position: string | null
  team: string | null
  market: string
  selected: boolean
  onOpen: () => void
}

function Player({ playerName, position, team, market, selected, onOpen }: PlayerProps) {
  return <span className="nba-prop-table__player">
    <span className="nba-prop-table__team" aria-hidden="true">{team ?? '--'}</span>
    <span>
      <button type="button" className="prop-table__open" aria-pressed={selected} onClick={onOpen}>{playerName}</button>
      <small>{position ? `${position} · ` : ''}{nbaMarketLabel(market)}</small>
    </span>
  </span>
}

function Line({ card }: { card: NbaPropCard }) {
  const payout = card.main.oddsType && card.main.oddsType !== 'standard' ? card.main.oddsType : 'standard'
  return <>
    <b>{card.main.line}</b>
    <small>{payout}{card.also.length ? ` · Also ${card.also.join(', ')}` : ''}</small>
  </>
}

function Sample({ card }: { card: NbaPropCard }) {
  const count = card.count === null ? '--' : card.count > 0 ? `over ${card.overCount} of ${card.count}` : 'No earlier games'
  return <>
    <span>{card.flagText ?? 'Reference only'}</span>
    <small>{count}</small>
  </>
}

function openFromRow(event: MouseEvent, open: () => void) {
  if (!(event.target instanceof Element && event.target.closest('button, a'))) open()
}

interface RowContextProps {
  market: string
  selected: boolean
  onOpen: () => void
  game?: NbaBoardGameContext
  now?: Date
  rowKey?: string
}

function GameCells({ game, now }: { game: NbaBoardGameContext, now: Date }) {
  const { tip, status } = nbaBoardGameLabels(game, now)
  return <>
    <td className="nba-board-table__game"><Link to={`/nba/game/${game.gameId}`}>{game.awayTeam} @ {game.homeTeam}</Link></td>
    <td className="nba-board-table__tip">{tip}{status && <small>{status}</small>}</td>
  </>
}

function PropRow({ card, market, selected, onOpen, game, now, rowKey }: RowContextProps & { card: NbaPropCard }) {
  return <tr data-row-key={rowKey} className={`is-row${selected ? ' is-selected' : ''}`} onClick={event => openFromRow(event, onOpen)}>
    <td className="prop-table__lead"><Player playerName={card.playerName} position={card.position} team={card.team} market={market} selected={selected} onOpen={onOpen} /></td>
    <td className="nba-prop-table__line" data-label="line"><Line card={card} /></td>
    <td className="is-num" data-label="model">{card.projectionRow?.projection ?? '--'}</td>
    <td className="prop-table__end is-num" data-label="gap">{card.projectionRow?.gap ?? '--'}</td>
    <td className="is-num" data-label="P(over)">{card.projectionRow?.pOver ?? '--'}</td>
    <td><MiniBars bars={lineOnlyBars(card)} empty="No earlier games" title={bar => `${nbaRecentValueLabel(market, bar.value)} vs ${bar.opponentTeam ?? '--'}`} /></td>
    <td className="nba-prop-table__sample"><Sample card={card} /></td>
    {game && <GameCells game={game} now={now ?? new Date()} />}
  </tr>
}

const COLUMNS: Array<[string, ReactNode]> = [
  ['player', 'Player'], ['line', 'Line'], ['model', 'Model'], ['gap', 'Gap'],
  ['probability', 'P(over)'], ['bars', 'Last 5'], ['sample', 'Sample'],
]
const NUMERIC = new Set(['model', 'gap', 'probability'])

/** One row per player and market, preserving NBA's existing card order and gray display rules. */
interface ModelledTableProps {
  market: string
  cards: NbaPropCard[]
  selectedPlayerId: number | null
  onOpen: (card: NbaPropCard) => void
}

export function NbaPropTable({ market, cards, selectedPlayerId, onOpen }: ModelledTableProps) {
  return <table className="prop-table nba-prop-table" aria-label={`${nbaMarketLabel(market)} props`}>
    <colgroup>{COLUMNS.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{COLUMNS.map(([key, label]) => <th key={key} className={NUMERIC.has(key) ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>{cards.map(card => <PropRow key={card.playerId} card={card} market={market} selected={card.playerId === selectedPlayerId} onOpen={() => onOpen(card)} />)}</tbody>
  </table>
}

function rungText(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

function LineOnlyRow({ row, market, selected, onOpen, game, now, rowKey }: RowContextProps & { row: NbaLineOnlyRow }) {
  const main = mainRung(row)
  const also = row.rungs.filter(rung => rung !== main).map(rung => rungText(rung.line, rung.oddsType)).join(' · ')
  const count = row.count === null ? '--' : row.count > 0 ? `over ${row.overCount} of ${row.count}` : 'No earlier games'
  return <tr data-row-key={rowKey} className={`is-row${selected ? ' is-selected' : ''}`} onClick={event => openFromRow(event, onOpen)}>
    <td className="prop-table__lead"><Player playerName={row.playerName} position={row.position} team={row.team} market={market} selected={selected} onOpen={onOpen} /></td>
    <td className="is-num" data-label="line">{main.line}<small>{main.oddsType ?? 'standard'}</small></td>
    <td className="nba-line-only-table__also" data-label="also">{also || '--'}</td>
    <td><MiniBars bars={lineOnlyBars(row)} empty="No earlier games" title={bar => `${nbaRecentValueLabel(market, bar.value)} vs ${bar.opponentTeam ?? '--'}`} /></td>
    <td className="prop-table__end" data-label="recent">{count}</td>
    {game && <GameCells game={game} now={now ?? new Date()} />}
  </tr>
}

const LINE_ONLY_COLUMNS: Array<[string, ReactNode]> = [
  ['player', 'Player'], ['line', 'Line'], ['also', 'Also'], ['bars', 'Last 5'], ['recent', 'Recent'],
]

interface LineOnlyTableProps {
  market: string
  rows: NbaLineOnlyRow[]
  selectedPlayerId: number | null
  onOpen: (row: NbaLineOnlyRow) => void
}

export function NbaLineOnlyTable({ market, rows, selectedPlayerId, onOpen }: LineOnlyTableProps) {
  return <table className="prop-table nba-line-only-table" aria-label={`${nbaMarketLabel(market)} other lines`}>
    <colgroup>{LINE_ONLY_COLUMNS.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{LINE_ONLY_COLUMNS.map(([key, label]) => <th key={key} className={key === 'line' ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>{rows.map(row => <LineOnlyRow key={row.playerId} row={row} market={market} selected={row.playerId === selectedPlayerId} onOpen={() => onOpen(row)} />)}</tbody>
  </table>
}

type BoardTableProps = {
  market: string
  selectedKey: string | null
  onOpen: (row: NbaBoardRow) => void
  now: Date
} & (
  { kind: 'modelled', rows: Extract<NbaBoardRow, { kind: 'modelled' }>[] } |
  { kind: 'line-only', rows: Extract<NbaBoardRow, { kind: 'line-only' }>[] }
)

export function NbaBoardTable(props: BoardTableProps) {
  const { market, selectedKey, onOpen, now } = props
  const modelled = props.kind === 'modelled'
  const columns: Array<[string, ReactNode]> = [
    ...(modelled ? COLUMNS : LINE_ONLY_COLUMNS), ['game', 'Game'], ['tip', 'Tip / status'],
  ]
  return <table className={`prop-table nba-board-table ${modelled ? 'nba-prop-table' : 'nba-line-only-table'}`} aria-label={`${nbaMarketLabel(market)} ${modelled ? 'props' : 'other lines'}`}>
    <colgroup>{columns.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{columns.map(([key, label]) => <th key={key} className={NUMERIC.has(key) || (!modelled && key === 'line') ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>{props.kind === 'modelled'
      ? props.rows.map(item => <PropRow key={item.key} rowKey={item.key} card={item.row} market={market} game={item.game} now={now} selected={item.key === selectedKey} onOpen={() => onOpen(item)} />)
      : props.rows.map(item => <LineOnlyRow key={item.key} rowKey={item.key} row={item.row} market={market} game={item.game} now={now} selected={item.key === selectedKey} onOpen={() => onOpen(item)} />)
    }</tbody>
  </table>
}
