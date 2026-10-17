import { Tooltip } from 'antd'
import type { CSSProperties } from 'react'
import type { TennisBoardCategory, TennisBoardLine } from '~/utils/tennisPropBoard'
import { marketLabel } from '~/utils/tennisPropBoard'
import { propCard, type TennisPropCardModel } from '~/utils/tennisPropCards'
import { tourTone } from '~/utils/tennisSlate'
import '~/components/tennis/tennis-slate.css'
import './tennis-prop-card.css'

const VISIBLE_FLAGS = 2

function CardTags({ card }: { card: TennisPropCardModel }) {
  const tone = tourTone(card.tour, card.tour)
  const extra = card.flags.length - VISIBLE_FLAGS
  return <span className="tennis-prop-card__tags">
    {tone && <span className={`tennis-tour-tag is-${tone}`}>{card.tour}</span>}
    {card.payoutTier && <span className={`tennis-prop-card__payout is-${card.payoutTier}`}>{card.payoutTier}</span>}
    {card.flags.slice(0, VISIBLE_FLAGS).map(flag => <span key={flag} className="tennis-prop-card__flag">{flag.replaceAll('_', ' ')}</span>)}
    {extra > 0 && <span className="tennis-prop-card__flag">+{extra}</span>}
  </span>
}

function HitBar({ card }: { card: TennisPropCardModel }) {
  const tone = card.evTone ? ` is-${card.evTone}` : ''
  return <span className="tennis-prop-card__prob">
    <span className="tennis-prop-card__hit">Hit <b>{card.hitPct == null ? '--' : `${card.hitPct.toFixed(0)}%`}</b></span>
    <span className={`tennis-prop-card__ev${tone}`}>{card.evText === '--' ? 'EV --' : `${card.evText} EV`}</span>
    {card.hitPct != null && card.breakEvenPct != null && <span className="tennis-prop-card__bar" style={{ '--p': `${card.hitPct}%`, '--be': `${card.breakEvenPct}%` } as CSSProperties}><span /></span>}
    {card.breakEvenLabel && <span className="tennis-prop-card__be">{card.breakEvenLabel}</span>}
  </span>
}

interface CardProps {
  row: TennisBoardLine
  rank: number | null
  selected: boolean
  onOpen: (row: TennisBoardLine) => void
}

export function TennisPropCard({ row, rank, selected, onOpen }: CardProps) {
  const card = propCard(row)
  const classes = ['tennis-prop-card', selected && 'is-selected', rank == null && 'is-dim'].filter(Boolean).join(' ')
  return <button type="button" className={classes} aria-pressed={selected} onClick={() => onOpen(row)}>
    <span className="tennis-prop-card__who">
      <span className="tennis-prop-card__rank">{rank ?? '--'}</span>
      <span className="tennis-prop-card__name"><strong>{card.playerName}</strong><small>{card.meta}</small><small>{card.startText}</small></span>
      {card.confidence && <span className="tennis-prop-card__tier">{card.confidence}</span>}
    </span>
    <CardTags card={card} />
    <span className="tennis-prop-card__line">
      <span><span className={`tennis-prop-card__pick${card.isUnder ? ' is-under' : ''}`}>{card.pickLabel}</span><b>{card.valueText}{card.unit && <small>{card.unit}</small>}</b><small className="tennis-prop-card__value-label">{card.valueLabel}</small></span>
      <span className="tennis-prop-card__proj">Model<b>{card.projectionText}</b></span>
    </span>
    <HitBar card={card} />
    <span className="tennis-prop-card__foot">
      <span>{card.opponentText}</span>
      <Tooltip title={card.flags.length ? card.flags.join(' · ') : 'No quality notes'}>
        <span className={`tennis-prop-card__trust${card.flags.length ? ' is-flagged' : ''}`}>{card.trust} · {card.source} · {card.sampleText}</span>
      </Tooltip>
    </span>
  </button>
}

interface GridProps {
  category: TennisBoardCategory
  showAll: boolean
  selectedId: number | null
  onOpen: (row: TennisBoardLine) => void
}

export function TennisPropCardGrid({ category, showAll, selectedId, onOpen }: GridProps) {
  const others = showAll ? category.other : []
  const card = (row: TennisBoardLine, rank: number | null) => <TennisPropCard key={`${row.source}-${row.id}`} row={row} rank={rank} selected={row.id === selectedId} onOpen={onOpen} />
  return <section className="tennis-prop-grid-wrap" aria-label={`${category.label} lines`}>
    {category.rateable.length
      ? <div className="tennis-prop-grid">{category.rateable.map((row, index) => card(row, index + 1))}</div>
      : <p className="tennis-prop-empty">No actionable {marketLabel(category.market).toLowerCase()} lines on this slate.</p>}
    {others.length > 0 && <>
      <div className="tennis-prop-divider"><strong>Not rateable</strong><small>Unlinked, stale, unsupported, or thin-sample lines remain visible for review but are excluded from the ranking.</small></div>
      <div className="tennis-prop-grid">{others.map(row => card(row, null))}</div>
    </>}
    {!category.rateable.length && !others.length && <p className="tennis-prop-empty">No lines in this category.</p>}
  </section>
}
