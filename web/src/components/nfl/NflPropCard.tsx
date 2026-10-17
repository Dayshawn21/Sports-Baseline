import { Tag, Tooltip } from 'antd'
import type { CSSProperties } from 'react'
import { FLAG_LABELS, formatHistoryValue, marketLabel } from '~/utils/nflLabels'
import type { NflBoardCategory, NflBoardLine } from '~/utils/nflPropBoard'
import { nflPropCard, recentBars, type NflPropCardModel } from '~/utils/nflPropCards'
import './nfl-prop-card.css'

const OTHER_LINES_NOTE = 'Alternate payouts, partial-game segments, and thin samples. The model does not price these against the market.'

function edgeNote(category: NflBoardCategory): string | null {
  if (category.referenceLine === null) return null
  return `Model minus line, then as a share of a typical ${marketLabel(category.market).toLowerCase()} line (${category.referenceLine.toFixed(1)}). Scoring against one shared line keeps players comparable; a row's own line can be small enough to make any gap look huge.`
}

function CardTags({ card }: { card: NflPropCardModel }) {
  if (!card.injury && !card.depthText) return null
  return <span className="nfl-prop-card__tags">
    {card.injury && <Tag color={card.injury.color}>{card.injury.label}</Tag>}
    {card.depthText && <span className="nfl-prop-card__tag">Depth: {card.depthText}</span>}
  </span>
}

function RecentBars({ row }: { row: NflBoardLine }) {
  const { bars, linePct } = recentBars(row)
  if (!bars.length) return <span className="nfl-prop-card__no-history">No completed history</span>
  const style = linePct === null ? undefined : { '--line': `${linePct}%` } as CSSProperties
  return <span className={`nfl-prop-card__bars${linePct === null ? '' : ' has-line'}`} style={style} aria-label={`Last ${bars.length} games`}>
    {bars.map((bar, index) => <span key={index} className={`is-${bar.vsLine ?? 'none'}`} style={{ '--h': `${bar.heightPct}%` } as CSSProperties} title={`${formatHistoryValue(row.market, bar.value)} vs ${bar.opponentTeam ?? '--'}`} />)}
  </span>
}

function CardHead({ card }: { card: NflPropCardModel }) {
  return <span className="nfl-prop-card__who">
    <span className="nfl-prop-card__badge" aria-hidden="true">{card.badge}</span>
    <span className="nfl-prop-card__name"><strong>{card.playerName}</strong><small>{card.meta}</small></span>
    <span className="nfl-prop-card__rank">{card.rank === null ? '--' : `#${card.rank}`}</span>
  </span>
}

function CardFoot({ card }: { card: NflPropCardModel }) {
  return <span className="nfl-prop-card__foot">
    <span className="nfl-prop-card__trust">{card.trust}</span>
    <Tooltip title={card.flags.length ? card.flags.map(flag => FLAG_LABELS[flag] ?? flag).join(' · ') : 'No quality notes'}>
      <span className={`nfl-prop-card__sample${card.thin ? ' is-thin' : ''}`}>{card.sampleText}</span>
    </Tooltip>
  </span>
}

/** Anytime TD is display only until 25c: the model beside the books, with no pick, edge or bars. */
function TdBody({ card }: { card: NflPropCardModel }) {
  return <>
    <span className="nfl-prop-card__probs">
      <span><small>Model</small><b>{card.modelText}</b></span>
      <span><small>Sportsbooks</small><b className="nfl-prop-card__book">{card.bookText}</b></span>
    </span>
    {card.snapText && <span className="nfl-prop-card__snap">Snap share · {card.snapText}</span>}
  </>
}

function StatBody({ card, row, note }: { card: NflPropCardModel, row: NflBoardLine, note: string | null }) {
  const side = card.pickLabel === '--' ? ' is-none' : card.isUnder ? ' is-negative' : ''
  return <>
    <span className="nfl-prop-card__line">
      <span className="nfl-prop-card__value"><small>Line</small><b>{card.lineText}</b><small>{card.unit}</small></span>
      <span className="nfl-prop-card__edge">
        <span className={`nfl-prop-card__pick${side}`}>{card.pickLabel}</span>
        <Tooltip title={note}><b className={`nfl-prop-card__share${side}`}>{card.edgeShareText}</b></Tooltip>
        <small>{card.edgeText}</small>
      </span>
      <span className="nfl-prop-card__model"><small>Model</small><b>{card.modelText}</b></span>
    </span>
    <RecentBars row={row} />
  </>
}

interface CardProps {
  row: NflBoardLine
  rank: number | null
  category: NflBoardCategory
  selected: boolean
  onOpen: (row: NflBoardLine) => void
}

export function NflPropCard({ row, rank, category, selected, onOpen }: CardProps) {
  const card = nflPropCard(row, rank, category.referenceLine, Date.now())
  const classes = ['nfl-prop-card', selected && 'is-selected', rank === null && 'is-dim'].filter(Boolean).join(' ')
  return <button type="button" className={classes} aria-pressed={selected} onClick={() => onOpen(row)}>
    <CardHead card={card} />
    <CardTags card={card} />
    {card.kind === 'td' ? <TdBody card={card} /> : <StatBody card={card} row={row} note={edgeNote(category)} />}
    <span className="nfl-prop-card__why" title={card.why}>{card.why}</span>
    <CardFoot card={card} />
  </button>
}

interface GridProps {
  category: NflBoardCategory
  showAll: boolean
  selectedLineId: number | null
  onOpen: (row: NflBoardLine) => void
}

export function NflPropCardGrid({ category, showAll, selectedLineId, onOpen }: GridProps) {
  const others = showAll ? category.other : []
  const card = (row: NflBoardLine, rank: number | null) => <NflPropCard key={row.lineId} row={row} rank={rank} category={category} selected={row.lineId === selectedLineId} onOpen={onOpen} />
  return <section className="nfl-prop-grid-wrap" aria-label={`${marketLabel(category.market)} lines`}>
    {category.rateable.length
      ? <div className="nfl-prop-grid">{category.rateable.map((row, index) => card(row, index + 1))}</div>
      : <p className="nfl-prop-empty">No rateable {marketLabel(category.market).toLowerCase()} lines this week.</p>}
    {others.length > 0 && <>
      <div className="nfl-prop-divider"><strong>Not rateable</strong><small>{OTHER_LINES_NOTE}</small></div>
      <div className="nfl-prop-grid">{others.map(row => card(row, null))}</div>
    </>}
  </section>
}
