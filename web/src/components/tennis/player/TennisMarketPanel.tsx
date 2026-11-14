import { Tag } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { PlayerEvidence } from '~/components/shared/PlayerEvidence'
import { PlayerLinesTable, type PlayerLinesRow } from '~/components/shared/PlayerLinesTable'
import { PlayerProjectionHero } from '~/components/shared/PlayerProjectionHero'
import { propMatchPath } from '~/utils/tennisMatchView'
import { tennisMarketHero } from '~/utils/tennisPlayerProps'
import { marketTitle, payoutTier, signalSummary, type TennisBoardLine } from '~/utils/tennisPropBoard'
import { propCard } from '~/utils/tennisPropCards'

interface LineRow { row: TennisBoardLine, review: boolean }

/** The side cell keeps the board's colors: gray unless a line was adopted, and an unadopted under never reads as a pick. */
function sideClass(row: TennisBoardLine): string {
  const card = propCard(row)
  if (card.adopted) return ''
  return card.pickLabel === '--' || card.payoutTier ? ' is-none' : card.isUnder ? ' is-negative' : ''
}

function linesRow({ row, review }: LineRow, selectedId: string | null): PlayerLinesRow {
  const card = propCard(row)
  return {
    key: card.key,
    propId: row.id,
    type: card.payoutTier ?? card.source,
    typeNote: review ? 'review' : undefined,
    line: card.valueText,
    gap: card.gapText ?? '--',
    selected: String(row.id) === selectedId,
    trailing: [
      { content: card.projectionText },
      { content: card.pickLabel, className: `tennis-prop-evidence__pick${sideClass(row)}` },
      { content: card.hitPct == null ? '--' : `${card.hitPct.toFixed(0)}%` },
      {
        content: <>{card.evText}{card.marginText && <small className="tennis-prop-evidence__margin">{card.marginText}</small>}</>,
        className: `tennis-prop-evidence__ev${card.evTone ? ` is-${card.evTone}` : ''}`,
      },
    ],
  }
}

function LineEvidence({ row }: { row: TennisBoardLine }) {
  const card = propCard(row)
  const inputs = Object.entries(row.projectionInputs ?? {})
  const flags = row.dataQualityFlags ?? []
  return <section className="nfl-prop-detail__section tennis-market-panel__evidence">
    <h4>{card.payoutTier ?? card.source} {card.valueText}</h4>
    <p><span>Why this line</span>{signalSummary(row)}</p>
    <p><span>Event</span>{[row.tournament, row.surface].filter(Boolean).join(' · ') || 'Unavailable'}</p>
    {inputs.length > 0 && <div><span>Projection inputs</span>{inputs.map(([key, value]) => <Tag key={key}>{key.replaceAll('_', ' ')}: {typeof value === 'number' ? value.toFixed(2) : value}</Tag>)}</div>}
    {flags.length > 0 && <div><span>Quality notes</span>{flags.map(flag => <Tag key={flag}>{flag.replaceAll('_', ' ')}</Tag>)}</div>}
  </section>
}

interface PanelProps {
  market: string
  rated: TennisBoardLine[]
  review: TennisBoardLine[]
  selectedId: string | null
  /** The match and form-window switches, then the recent-form chart for the first line. */
  form: ReactNode
}

/** One market's panel for the selected match, in the shared player-page order: projection, recent form, lines, then closed evidence. */
export function TennisMarketPanel({ market, rated, review, selectedId, form }: PanelProps) {
  const lines: LineRow[] = [...rated.map(row => ({ row, review: false })), ...review.map(row => ({ row, review: true }))]
  const hero = tennisMarketHero(lines.map(line => line.row))
  const first = lines[0]?.row ?? null
  const matchPath = first ? propMatchPath(first) : null
  // Moneyline and sportsbook rows can still carry a colored side, so the caption only claims what is true of PrizePicks lines.
  const prizePicksOnly = lines.length > 0 && lines.every(({ row }) => payoutTier(row) != null)
  return <section className="nfl-player-card nfl-player-prop" aria-label={marketTitle(market)}>
    <div className="nfl-player-card__head">
      <h3 className="nfl-player-prop__title">{marketTitle(market)}</h3>
      <span className="nfl-player-muted">{first ? propCard(first).startText : ''}{matchPath && <> · <Link to={matchPath}>Open match</Link></>}</span>
    </div>
    <div className="nfl-player-prop__body player-market">
      {hero && <PlayerProjectionHero hero={hero} />}
      <section className="nfl-prop-detail__section">{form}</section>
      <PlayerLinesTable title="Lines" columns={['gap']} trailing={['Model', 'Side', 'Hit', 'EV']} rows={lines.map(line => linesRow(line, selectedId))}
        intro={prizePicksOnly && <p className="player-lines__tier-note tennis-market-panel__reference">Model, Hit and EV are reference, not picks. A side to take shows only on an adopted line.</p>} />
      <PlayerEvidence contents="Why each line, event, projection inputs, quality notes">
        {lines.map(({ row }) => <LineEvidence key={`${row.source}-${row.id}`} row={row} />)}
      </PlayerEvidence>
    </div>
  </section>
}
