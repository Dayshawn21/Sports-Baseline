import { useState } from 'react'
import type { BestPick, PropLine } from '~/types/tennis'
import type { UnifiedTennisMatch } from '~/utils/unifiedTennis'
import { anglePicks, bestBetPicks, unifiedMatchToPrediction } from '~/utils/unifiedTennis'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtSurface, fmtStartCT, fmtTournament } from '~/utils/format'
import { getDisplayFlagLabel, getDisplayFlags } from '~/components/tennis/qualityFlags'

interface Props {
  match: UnifiedTennisMatch
  onOpenMatch?: () => void
}

const TOUR_COLORS: Record<string, string> = {
  ATP: 'var(--atp-blue)',
  WTA: 'var(--wta-pink)',
  CHALLENGER: 'var(--challenger-teal)',
}

const CONFIDENCE_STYLES: Record<string, { color: string; background: string; border: string }> = {
  LOCK: { color: 'var(--positive)', background: 'var(--positive-soft)', border: 'color-mix(in srgb, var(--positive) 30%, transparent)' },
  STRONG: { color: 'var(--positive)', background: 'transparent', border: 'color-mix(in srgb, var(--positive) 35%, transparent)' },
  LEAN: { color: 'var(--caution)', background: 'var(--caution-soft)', border: 'color-mix(in srgb, var(--caution) 32%, transparent)' },
}

function ConfidenceBadge({ confidence }: { confidence: string | null | undefined }) {
  const style = CONFIDENCE_STYLES[confidence ?? ''] ?? CONFIDENCE_STYLES.STRONG
  return (
    <span className="unified-confidence" style={{ color: style.color, background: style.background, borderColor: style.border }}>
      {confidence ?? '—'}
    </span>
  )
}

function edgeLabel(edge: number | null | undefined) {
  if (edge == null || !Number.isFinite(edge)) return '—'
  return `${edge >= 0 ? '+' : ''}${edge.toFixed(1)}%`
}

function qualityLabel(flags: string[] | null | undefined, oddsSource: string | null | undefined) {
  const labels = [...(flags ?? [])]
  if (oddsSource === 'imputed' && !labels.includes('imputed_odds')) labels.push('imputed_odds')
  return labels.map((flag) => flag.replaceAll('_', ' ')).join(', ')
}

function BestPickRow({ pick, bettable = false }: { pick: BestPick; bettable?: boolean }) {
  const quality = qualityLabel(pick.dataQualityFlags, pick.oddsSource)
  return (
    <div className="unified-pick-row" title={pick.reasoning}>
      <div>
        <div className="unified-pick-name">{pick.pick}</div>
        <div className="unified-pick-reason">{pick.reasoning}</div>
        {bettable && (
          <div className="unified-pick-meta">
            <span>Model {fmtPct(pick.modelProb)}</span>
            <span>Market {fmtPct(pick.marketProb)}</span>
            <span>{pick.evPct != null ? `${edgeLabel(pick.evPct)} EV` : 'EV —'}</span>
            <span>{pick.kellyFraction != null ? `${(pick.kellyFraction * 100).toFixed(1)}% Kelly` : 'Kelly —'}</span>
            {quality && <span>{quality}</span>}
          </div>
        )}
      </div>
      <ConfidenceBadge confidence={pick.confidence} />
      <span className="unified-edge">{edgeLabel(pick.edgePct)}</span>
    </div>
  )
}

function PropRow({ prop }: { prop: PropLine }) {
  const [expanded, setExpanded] = useState(false)
  const line = prop.line == null ? null : Number(prop.line)
  const recommendation = prop.recommendation?.toUpperCase() ?? '—'
  // demon/goblin share a line with the standard pick but pay differently, so the
  // tier has to be visible or two rows look like duplicates.
  const oddsType = (prop.oddsType ?? '').toLowerCase()
  const tier = oddsType === 'demon' || oddsType === 'goblin' ? oddsType : null

  return (
    <div className="unified-prop">
      <button
        type="button"
        className="unified-prop-row"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        <span className="unified-prop-player">
          {prop.playerName?.trim() || 'Unknown player'}
          {tier && <span className={`unified-pp-tier is-${tier}`}>{tier}</span>}
        </span>
        <span className="unified-prop-market">{prop.statType}</span>
        <span className={`unified-direction is-${recommendation.toLowerCase()}`}>{recommendation}</span>
        <span className="unified-prop-line">{line != null && !Number.isNaN(line) ? line.toFixed(1) : '—'}</span>
        {/* EV, not the projection-vs-line delta: the delta ignores payout, so a
            goblin priced at a near-certain line looked like a huge edge. */}
        <span className="unified-edge" title="Expected return per unit staked">
          {prop.evPct != null ? `${edgeLabel(prop.evPct)} EV` : edgeLabel(null)}
        </span>
        <ConfidenceBadge confidence={prop.confidence} />
        <span className="unified-expand" aria-hidden="true">{expanded ? '−' : '+'}</span>
      </button>
      {expanded && (
        <div className="unified-prop-analysis">
          <div><span>Projection</span><strong>{prop.statAvg != null ? prop.statAvg.toFixed(2) : 'Unavailable'}</strong></div>
          <div><span>Projection vs line</span><strong>{edgeLabel(prop.edgePct)}</strong></div>
          <div><span>Hit probability</span><strong>{fmtPct(prop.hitProbability)}</strong></div>
          <div>
            <span>Break-even needed</span>
            <strong>{prop.breakEvenPct != null ? `${prop.breakEvenPct.toFixed(1)}%` : '—'}</strong>
          </div>
          <div><span>Sample</span><strong>{prop.matchesCount ?? '—'} matches</strong></div>
          <div><span>Over probability</span><strong>{fmtPct(prop.pOver)}</strong></div>
          <div><span>Under probability</span><strong>{fmtPct(prop.pUnder)}</strong></div>
          {prop.opponentStatAvg != null && <div><span>Opponent allowed</span><strong>{prop.opponentStatAvg.toFixed(2)}</strong></div>}
          {prop.projectionStatus && prop.projectionStatus !== 'ok' && (
            <div className="unified-analysis-warning"><span>Status</span><strong>{prop.projectionStatus.replaceAll('_', ' ')}</strong></div>
          )}
        </div>
      )}
    </div>
  )
}

export default function UnifiedMatchCard({ match, onOpenMatch }: Props) {
  const prediction = unifiedMatchToPrediction(match)
  const tour = prediction?.tour ?? 'TENNIS'
  // Colour still keys on the raw tour so WTA 125 keeps the Challenger accent.
  const tourColor = TOUR_COLORS[tour] ?? 'var(--text-muted)'
  const tourLabel = prediction?.tourLabel || tour
  const surface = fmtSurface(prediction?.surface ?? null)
  const probability = prediction?.p1WinProb ?? 0.5
  const p1Pct = Math.round(probability * 100)
  const bestBets = bestBetPicks(match)
  const angles = anglePicks(match)
  const lockCount = [...bestBets, ...match.props].filter((item) => item.confidence === 'LOCK').length
  const strongCount = [...bestBets, ...match.props].filter((item) => item.confidence === 'STRONG').length
  const flags = prediction ? getDisplayFlags(prediction.qualityFlags).slice(0, 2) : []
  // Prop-only groups carry no prediction and no matchId, so neither a tournament
  // nor "Match <id>" is available — name them by the players the props belong to.
  const propPlayerNames = [...new Set(match.props.map((prop) => prop.playerName).filter(Boolean))]
  const headerLabel = prediction
    ? fmtTournament(prediction.tournament)
    : propPlayerNames.join(' · ') || 'Unlinked props'
  // Carries the day too when the match is not today — the board is often
  // showing tomorrow's card and a bare clock time reads as "later today".
  const headerTime = fmtStartCT(prediction?.startUtc ?? match.props[0]?.startTime)

  return (
    <article className="unified-match-card" style={{ '--tour-accent': tourColor } as React.CSSProperties}>
      <button
        type="button"
        className="unified-match-summary"
        onClick={onOpenMatch}
        disabled={!onOpenMatch}
      >
        <div className="unified-card-meta">
          <span>
            {headerLabel}
            {prediction?.round ? ` · ${prediction.round}` : ''}
            {headerTime ? ` · ${headerTime}` : ''}
          </span>
          <span className="unified-card-badges">
            {surface && <span>{surface}</span>}
            <span>{tourLabel}</span>
          </span>
        </div>

        {prediction ? (
          <>
            <div className="unified-players">
              <div>
                <strong>{prediction.p1Name}</strong>
                <span>{fmtAmerican(prediction.p1OddsAmerican)} · {fmtPct(prediction.p1WinProb)}</span>
              </div>
              <span className="unified-vs">VS</span>
              <div className="unified-player-two">
                <strong>{prediction.p2Name}</strong>
                <span>{fmtAmerican(prediction.p2OddsAmerican)} · {fmtPct(prediction.p2WinProb)}</span>
              </div>
            </div>
            <div className="unified-probability" aria-label={`${prediction.p1Name} win probability ${p1Pct}%`}>
              <span style={{ width: `${p1Pct}%` }} />
            </div>
          </>
        ) : (
          <div className="unified-prop-only-title">
            Prediction unavailable · {match.props.length} player {match.props.length === 1 ? 'prop' : 'props'}
          </div>
        )}

        <div className="unified-card-counts">
          {lockCount > 0 && <span className="is-lock">{lockCount} {lockCount === 1 ? 'Lock' : 'Locks'}</span>}
          {strongCount > 0 && <span className="is-strong">{strongCount} Strong</span>}
          {flags.map((flag) => (
            <span key={flag} className="unified-quality-flag">
              {prediction ? getDisplayFlagLabel(prediction, flag) : flag}
            </span>
          ))}
          {match.inferredPropLink && (
            <span className="unified-quality-flag" title="Props matched by player name, not by match id">
              Inferred link
            </span>
          )}
          {onOpenMatch && <span className="unified-open-analysis">Open match analysis →</span>}
        </div>
      </button>

      {bestBets.length > 0 && (
        <section className="unified-card-section">
          <div className="unified-card-section-title">Best Bets</div>
          {bestBets.map((pick, index) => (
            <BestPickRow key={`${pick.pickType}-${pick.pick}-${index}`} pick={pick} bettable />
          ))}
        </section>
      )}

      {angles.length > 0 && (
        <section className="unified-card-section">
          <div className="unified-card-section-title">Angles</div>
          {angles.map((pick, index) => (
            <BestPickRow key={`${pick.pickType}-${pick.pick}-${index}`} pick={pick} />
          ))}
        </section>
      )}

      {match.props.length > 0 && (
        <section className="unified-card-section unified-props-section">
          <div className="unified-card-section-title">Player props</div>
          {match.props.map((prop) => <PropRow key={prop.id} prop={prop} />)}
        </section>
      )}
    </article>
  )
}
