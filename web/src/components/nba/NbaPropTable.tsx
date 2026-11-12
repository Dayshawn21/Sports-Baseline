import type { MouseEvent, ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AltLinesChip } from '~/components/shared/AltLinesChip'
import { MiniBars } from '~/components/shared/MiniBars'
import { ProbabilityRing } from '~/components/shared/ProbabilityRing'
import { StatStrip } from '~/components/shared/StatStrip'
import { NbaInjuryTag } from '~/components/nba/NbaInjury'
import type { NbaInjury, NbaInjuryReport, NbaLineOnlyRecent } from '~/types/nba'
import { nbaInjuryFreshness } from '~/utils/nbaInjuries'
import { nbaMarketLabel, nbaRecentValueLabel, type NbaLineOnlyRow } from '~/utils/nbaLineOnly'
import { lineOnlyBars, mainRung, type NflLineOnlyRung } from '~/utils/nflLineOnly'
import type { NbaPropCard } from '~/utils/nbaProps'
import { nbaBoardGameLabels, type NbaBoardGameContext, type NbaBoardRow } from '~/utils/nbaPropBoard'
import { REFERENCE, groupAltLines, probabilityRing, statStrip } from '~/utils/propRowVisuals'
import '~/components/shared/prop-table.css'
import './nba-prop-table.css'

interface PlayerProps {
  playerName: string
  position: string | null
  team: string | null
  market: string
  to: string
  linkState: unknown
  injury: NbaInjury | null
  freshness: NbaInjuryReport['freshness']
}

function Player({ playerName, position, team, market, to, linkState, injury, freshness }: PlayerProps) {
  return <span className="nba-prop-table__player">
    <span className="nba-prop-table__team" aria-hidden="true">{team ?? '--'}</span>
    <span>
      <Link className="prop-table__open" to={to} state={linkState}>{playerName}</Link>
      <small>{position ? `${position} · ` : ''}{nbaMarketLabel(market)}</small>
      <NbaInjuryTag injury={injury} freshness={freshness} />
    </span>
  </span>
}

function Line({ card, market }: { card: NbaPropCard, market: string }) {
  const payout = card.main.oddsType && card.main.oddsType !== 'standard' ? card.main.oddsType : 'standard'
  return <>
    <b>{card.main.line}</b>
    <AltLinesChip labels={card.also} context={nbaMarketLabel(market)} />
    <small>{payout}</small>
  </>
}

function Probability({ card }: { card: NbaPropCard }) {
  const text = card.projectionRow?.pOver ?? null
  if (text === null) return <>--</>
  return <><ProbabilityRing ring={probabilityRing(card.main.pOver === null ? null : card.main.pOver * 100, REFERENCE)} />{text}</>
}

function Sample({ card }: { card: NbaPropCard }) {
  const count = card.count === null ? '--' : card.count > 0 ? `over ${card.overCount} of ${card.count}` : 'No earlier games'
  return <>
    <span>{card.flagText ?? 'Reference only'}</span>
    <small>{count}</small>
  </>
}

/** The bars and the stat strip read the same games against the same main line. */
function RecentGames({ row, market }: { row: { rungs: NflLineOnlyRung[], recent: NbaLineOnlyRecent[] }, market: string }) {
  const values = row.recent.flatMap(game => game.value === null ? [] : [game.value])
  const line = row.rungs.length ? mainRung(row).line : null
  return <>
    <MiniBars bars={lineOnlyBars(row)} empty="No earlier games" title={bar => `${nbaRecentValueLabel(market, bar.value)} vs ${bar.opponentTeam ?? '--'}`} />
    <StatStrip cells={statStrip(values, line, REFERENCE)} />
  </>
}

function followFromRow(event: MouseEvent, follow: () => void) {
  if (!(event.target instanceof Element && event.target.closest('button, a'))) follow()
}

interface RowContextProps {
  market: string
  /** The player page for this row's player; the name links to it and a plain click on the row follows it. */
  pathFor: (playerId: number) => string
  linkState?: unknown
  game?: NbaBoardGameContext
  now?: Date
  injuryReport?: NbaInjuryReport
  startUtc?: string | null
}

function GameCells({ game, now }: { game: NbaBoardGameContext, now: Date }) {
  const { tip, status } = nbaBoardGameLabels(game, now)
  return <>
    <td className="nba-board-table__game"><Link to={`/nba/game/${game.gameId}`}>{game.awayTeam} @ {game.homeTeam}</Link></td>
    <td className="nba-board-table__tip">{tip}{status && <small>{status}</small>}</td>
  </>
}

function PropRow({ card, market, pathFor, linkState, game, now, injuryReport, startUtc }: RowContextProps & { card: NbaPropCard }) {
  const navigate = useNavigate()
  const to = pathFor(card.playerId)
  const freshness = nbaInjuryFreshness(game?.injuryReport ?? injuryReport, game?.startUtc ?? startUtc ?? null, now ?? new Date())
  return <tr className="is-row" onClick={event => followFromRow(event, () => navigate(to, { state: linkState }))}>
    <td className="prop-table__lead"><Player playerName={card.playerName} position={card.position} team={card.team} market={market} to={to} linkState={linkState} injury={card.injury} freshness={freshness} /></td>
    <td className="nba-prop-table__line" data-label="line"><Line card={card} market={market} /></td>
    <td className="is-num" data-label="model">{card.projectionRow?.projection ?? '--'}</td>
    <td className="prop-table__end is-num" data-label="gap">{card.projectionRow?.gap ?? '--'}</td>
    <td className="is-num" data-label="P(over)"><Probability card={card} /></td>
    <td><RecentGames row={card} market={market} /></td>
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
  pathFor: (playerId: number) => string
  injuryReport: NbaInjuryReport
  startUtc: string | null
  now: Date
}

export function NbaPropTable({ market, cards, pathFor, injuryReport, startUtc, now }: ModelledTableProps) {
  return <table className="prop-table nba-prop-table" aria-label={`${nbaMarketLabel(market)} props`}>
    <colgroup>{COLUMNS.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{COLUMNS.map(([key, label]) => <th key={key} className={NUMERIC.has(key) ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>{cards.map(card => <PropRow key={card.playerId} card={card} market={market} pathFor={pathFor} injuryReport={injuryReport} startUtc={startUtc} now={now} />)}</tbody>
  </table>
}

function rungText(line: number, oddsType: string | null): string {
  return oddsType && oddsType !== 'standard' ? `${line} ${oddsType}` : `${line}`
}

function LineOnlyRow({ row, market, pathFor, linkState, game, now, injuryReport, startUtc }: RowContextProps & { row: NbaLineOnlyRow }) {
  const navigate = useNavigate()
  const to = pathFor(row.playerId)
  const freshness = nbaInjuryFreshness(game?.injuryReport ?? injuryReport, game?.startUtc ?? startUtc ?? null, now ?? new Date())
  const main = mainRung(row)
  const alts = groupAltLines(row.rungs)?.alts.map(rung => rungText(rung.line, rung.oddsType)) ?? []
  const count = row.count === null ? '--' : row.count > 0 ? `over ${row.overCount} of ${row.count}` : 'No earlier games'
  return <tr className="is-row" onClick={event => followFromRow(event, () => navigate(to, { state: linkState }))}>
    <td className="prop-table__lead"><Player playerName={row.playerName} position={row.position} team={row.team} market={market} to={to} linkState={linkState} injury={row.injury} freshness={freshness} /></td>
    <td className="is-num" data-label="line">{main.line}<small>{main.oddsType ?? 'standard'}</small></td>
    <td className="nba-line-only-table__also" data-label="also">{alts.length ? <AltLinesChip labels={alts} context={nbaMarketLabel(market)} /> : '--'}</td>
    <td><RecentGames row={row} market={market} /></td>
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
  pathFor: (playerId: number) => string
  injuryReport: NbaInjuryReport
  startUtc: string | null
  now: Date
}

export function NbaLineOnlyTable({ market, rows, pathFor, injuryReport, startUtc, now }: LineOnlyTableProps) {
  return <table className="prop-table nba-line-only-table" aria-label={`${nbaMarketLabel(market)} other lines`}>
    <colgroup>{LINE_ONLY_COLUMNS.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{LINE_ONLY_COLUMNS.map(([key, label]) => <th key={key} className={key === 'line' ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>{rows.map(row => <LineOnlyRow key={row.playerId} row={row} market={market} pathFor={pathFor} injuryReport={injuryReport} startUtc={startUtc} now={now} />)}</tbody>
  </table>
}

type BoardTableProps = {
  market: string
  pathFor: (playerId: number) => string
  linkState?: unknown
  now: Date
} & (
  { kind: 'modelled', rows: Extract<NbaBoardRow, { kind: 'modelled' }>[] } |
  { kind: 'line-only', rows: Extract<NbaBoardRow, { kind: 'line-only' }>[] }
)

export function NbaBoardTable(props: BoardTableProps) {
  const { market, pathFor, linkState, now } = props
  const modelled = props.kind === 'modelled'
  const columns: Array<[string, ReactNode]> = [
    ...(modelled ? COLUMNS : LINE_ONLY_COLUMNS), ['game', 'Game'], ['tip', 'Tip / status'],
  ]
  return <table className={`prop-table nba-board-table ${modelled ? 'nba-prop-table' : 'nba-line-only-table'}`} aria-label={`${nbaMarketLabel(market)} ${modelled ? 'props' : 'other lines'}`}>
    <colgroup>{columns.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{columns.map(([key, label]) => <th key={key} className={NUMERIC.has(key) || (!modelled && key === 'line') ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>{props.kind === 'modelled'
      ? props.rows.map(item => <PropRow key={item.key} card={item.row} market={market} game={item.game} now={now} pathFor={pathFor} linkState={linkState} />)
      : props.rows.map(item => <LineOnlyRow key={item.key} row={item.row} market={market} game={item.game} now={now} pathFor={pathFor} linkState={linkState} />)
    }</tbody>
  </table>
}
