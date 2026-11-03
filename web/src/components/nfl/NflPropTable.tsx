import { Tag, Tooltip } from 'antd'
import type { MouseEvent, ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MiniBars } from '~/components/shared/MiniBars'
import { rememberOpened } from '~/hooks/useRestoreOpenedRow'
import { FLAG_LABELS, formatHistoryValue, marketLabel } from '~/utils/nflLabels'
import type { NflBoardCategory, NflBoardLine } from '~/utils/nflPropBoard'
import { openedRowKey } from '~/utils/nflOpenedRow'
import { FROM_BOARD, nflPlayerMarketLink } from '~/utils/nflPlayer'
import { nflPropCard, recentBars, type NflPropCardModel } from '~/utils/nflPropCards'
import { isTargetsReference, TARGETS_REFERENCE_NOTE } from '~/utils/nflTargets'
import '~/components/shared/prop-table.css'
import './nfl-prop-table.css'

const OTHER_LINES_NOTE = 'Alternate payouts, partial-game segments, and thin samples. The model does not price these against the market.'

export interface NflPropTableRow {
  row: NflBoardLine
  rank: number | null
}

function edgeNote(category: NflBoardCategory): string | null {
  if (category.referenceLine === null) return null
  return `Model minus line, then as a share of a typical ${marketLabel(category.market).toLowerCase()} line (${category.referenceLine.toFixed(1)}). Scoring against one shared line keeps players comparable; a row's own line can be small enough to make any gap look huge.`
}

function Player({ card, row, to, inGame }: { card: NflPropCardModel, row: NflBoardLine, to: string, inGame: boolean }) {
  // The badge falls back to the position, which the meta line already leads with.
  const team = card.badge === (row.position ?? '--') ? '' : `${card.badge} · `
  const meta = inGame ? card.gameMeta : card.meta
  return <>
    <span className="prop-table__player-name">
      <Link className="prop-table__open" to={to} state={inGame ? undefined : FROM_BOARD} data-open-key={openedRowKey('table', row.lineId)} onClick={() => rememberOpened('table', row.lineId)}>{card.playerName}</Link>
      {card.injury && <Tag color={card.injury.color}>{card.injury.label}</Tag>}
      {card.depthText && <span className="prop-table__tag">Depth: {card.depthText}</span>}
    </span>
    <small title={`${team}${meta}`}>{team}{meta}</small>
  </>
}

function Gap({ card, note }: { card: NflPropCardModel, note: string | null }) {
  if (card.kind === 'reference') return <>
    <Tooltip title={TARGETS_REFERENCE_NOTE}><b className="nfl-prop-table__share is-reference">{card.edgeText}</b></Tooltip>
    <small>reference gap</small>
  </>
  const side = card.pickLabel === '--' ? ' is-none' : card.isUnder ? ' is-negative' : ''
  return <>
    <span className={`nfl-prop-table__pick${side}`}>{card.pickLabel}</span>{' '}
    <Tooltip title={note}><b className={`nfl-prop-table__share${side}`}>{card.edgeShareText}</b></Tooltip>
    <small>{card.edgeText}</small>
  </>
}

function Sample({ card }: { card: NflPropCardModel }) {
  return <>
    <span className="nfl-prop-table__trust">{card.trust}</span>
    <Tooltip title={card.flags.length ? card.flags.map(flag => FLAG_LABELS[flag] ?? flag).join(' · ') : 'No quality notes'}>
      <small className={card.thin ? 'is-thin' : ''}>{card.sampleText}</small>
    </Tooltip>
  </>
}

interface RowProps {
  item: NflPropTableRow
  category: NflBoardCategory
  inGame: boolean
  now: number
}

function PropRow({ item: { row, rank }, category, inGame, now }: RowProps) {
  const navigate = useNavigate()
  const to = nflPlayerMarketLink(row.playerId, row.market)
  const card = nflPropCard(row, rank, category.referenceLine, now)
  const classes = ['is-row', card.rank === null && card.kind !== 'reference' && 'is-dim'].filter(Boolean).join(' ')
  // Links and the mini bars handle their own clicks; a modified click keeps the browser's new-tab behavior.
  const open = (event: MouseEvent) => {
    const plain = event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey
    if (!plain || (event.target instanceof Element && event.target.closest('a, button'))) return
    rememberOpened('table', row.lineId)
    navigate(to, { state: inGame ? undefined : FROM_BOARD })
  }
  const player = <td className="prop-table__player"><Player card={card} row={row} to={to} inGame={inGame} /></td>
  const rankCell = <td className="prop-table__lead prop-table__rank">{card.rank === null ? '--' : `#${card.rank}`}</td>
  if (card.kind === 'td') {
    return <tr className={classes} title={card.why} onClick={open}>
      {rankCell}{player}
      <td className="prop-table__end is-num">{card.modelText}</td>
      <td className="nfl-prop-table__books" data-label="books">{card.bookText}</td>
      <td className="nfl-prop-table__snap" data-label="snap">{card.snapText ?? '--'}</td>
      <td><Sample card={card} /></td>
    </tr>
  }
  return <tr className={classes} title={card.why} onClick={open}>
    {rankCell}{player}
    <td className="is-num" data-label="line">{card.lineText}</td>
    <td className="is-num" data-label={card.kind === 'reference' ? 'reference' : 'model'}>{card.modelText}</td>
    <td className="prop-table__end is-num nfl-prop-table__gap"><Gap card={card} note={edgeNote(category)} /></td>
    <td className="nfl-prop-table__bars"><MiniBars interactive={inGame} bars={recentBars(row)} empty="No history" valueLabel={bar => String(bar.value)} lineLabel={card.lineText} showOpponents title={bar => `${formatHistoryValue(row.market, bar.value)} vs ${bar.opponentTeam ?? '--'}`} /></td>
    <td><Sample card={card} /></td>
  </tr>
}

const STAT_COLUMNS: Array<[string, ReactNode]> = [['rank', '#'], ['player', 'Player'], ['line', 'Line'], ['model', 'Model'], ['gap', 'Gap'], ['bars', 'Last 5'], ['sample', 'Sample']]
const TD_COLUMNS: Array<[string, ReactNode]> = [['rank', '#'], ['player', 'Player'], ['model', 'Model'], ['books', 'Sportsbooks'], ['snap', 'Snap share'], ['sample', 'Sample']]
const NUMERIC = new Set(['line', 'model', 'gap'])

interface Props {
  category: NflBoardCategory
  rateable: NflPropTableRow[]
  other: NflPropTableRow[]
  now: number
  /** On a game page the rows drop the matchup and kickoff the page already shows. */
  inGame?: boolean
}

/** One market's lines, one row each, ranked as the board ranks them; a row opens the player page. Gray until 27h. */
export function NflPropTable({ category, rateable, other, now, inGame = false }: Props) {
  const td = category.market === 'anytime_touchdown'
  const reference = isTargetsReference(category.market)
  const columns = td ? TD_COLUMNS : STAT_COLUMNS.map(([key, label]): [string, ReactNode] => [key, reference && key === 'model' ? 'Reference' : label])
  const row = (item: NflPropTableRow) => <PropRow key={item.row.lineId} item={item} category={category} inGame={inGame} now={now} />
  return <table className={`prop-table nfl-prop-table${td ? ' is-td' : ''}`} aria-label={`${marketLabel(category.market)} lines`}>
    {reference && <caption className="nfl-prop-table__reference-note">{TARGETS_REFERENCE_NOTE} Rows are unranked.</caption>}
    <colgroup>{columns.map(([key]) => <col key={key} className={`is-${key}`} />)}</colgroup>
    <thead><tr>{columns.map(([key, label]) => <th key={key} className={NUMERIC.has(key) || (td && key === 'model') ? 'is-num' : undefined}>{label}</th>)}</tr></thead>
    <tbody>
      {rateable.map(row)}
      {other.length > 0 && <tr className="prop-table__divider"><td colSpan={columns.length}><strong>Not rateable</strong><small>{OTHER_LINES_NOTE}</small></td></tr>}
      {other.map(row)}
    </tbody>
  </table>
}
