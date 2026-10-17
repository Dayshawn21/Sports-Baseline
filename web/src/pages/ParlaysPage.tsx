import { useState } from 'react'
import { Select, DatePicker } from 'antd'
import { useBankrollBuilder } from '~/hooks/useBankrollBuilder'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtTournament, fmtTimeCT } from '~/utils/format'
import LoadingState from '~/components/shared/LoadingState'
import ErrorState from '~/components/shared/ErrorState'
import StatChip from '~/components/shared/StatChip'
import type { BankrollPick, SuggestedParlay } from '~/types/tennis'
import { useIsMobile } from '~/hooks/useIsMobile'
import { withAlpha } from '~/utils/color'

// ── Theme & colors ──────────────────────────────────────────────────────────

const TOUR_COLORS: Record<string, string> = {
  ATP: 'var(--atp-blue)',
  WTA: 'var(--wta-pink)',
  CHALLENGER: 'var(--challenger-teal)',
}

const BET_TYPE_CONFIG: Record<string, { label: string; color: string; short: string }> = {
  ml:           { label: 'Moneyline',     color: 'var(--text-secondary)', short: 'ML' },
  '2-0':        { label: 'Straight Sets', color: 'var(--text-secondary)', short: '2-0' },
  '3-0':        { label: 'Straight Sets', color: 'var(--text-secondary)', short: '3-0' },
  underdog_set: { label: 'Underdog Set',  color: 'var(--text-secondary)', short: 'U-SET' },
  total_games:  { label: 'Total Games',   color: 'var(--caution)', short: 'TOTAL' },
}

const CONF_STYLES: Record<string, { color: string; bg: string; border: string }> = {
  LOCK:   { color: 'var(--positive)', bg: 'var(--positive-soft)',   border: 'color-mix(in srgb, var(--positive) 30%, transparent)' },
  STRONG: { color: 'var(--positive)', bg: 'transparent',  border: 'color-mix(in srgb, var(--positive) 35%, transparent)' },
  LEAN:   { color: 'var(--caution)', bg: 'var(--caution-soft)',  border: 'color-mix(in srgb, var(--caution) 30%, transparent)' },
  PASS:   { color: 'var(--text-muted)', bg: 'var(--bg-raised)', border: 'var(--bg-raised)' },
}

/** Column template for the singles table — the row adds a trailing action column. */
const SINGLES_COLS = '32px 60px minmax(200px, 0.85fr) minmax(240px, 1.6fr) auto auto auto auto'

// ── Sub-components ──────────────────────────────────────────────────────────

function BetTypeBadge({ betType }: { betType: string }) {
  const cfg = BET_TYPE_CONFIG[betType] ?? { label: betType, color: 'var(--text-muted)', short: betType.slice(0, 3).toUpperCase() }
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: 9,
      fontWeight: 800,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: cfg.color,
      background: withAlpha(cfg.color, 0.082),
      border: `1px solid ${withAlpha(cfg.color, 0.188)}`,
      borderRadius: 3,
      padding: '2px 7px',
      lineHeight: '14px',
      whiteSpace: 'nowrap',
    }}>
      {cfg.short}
    </span>
  )
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const s = CONF_STYLES[confidence] ?? CONF_STYLES.PASS
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: 9,
      fontWeight: 800,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: s.color,
      background: s.bg,
      border: `1px solid ${s.border}`,
      borderRadius: 3,
      padding: '2px 8px',
      whiteSpace: 'nowrap',
    }}>
      {confidence}
    </span>
  )
}

function SinglePickRow({ pick, rank }: { pick: BankrollPick; rank: number }) {
  const tourColor = TOUR_COLORS[pick.tour] ?? 'var(--text-secondary)'
  const edgePositive = pick.edgePct >= 0

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: SINGLES_COLS,
        gap: 12,
        alignItems: 'center',
        padding: '12px 18px',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        transition: 'background 0.12s ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.02)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
    >
      {/* Rank */}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 14,
        fontWeight: 700,
        color: rank <= 3 ? 'var(--positive)' : 'var(--text-secondary)',
        textAlign: 'center',
      }}>
        #{rank}
      </span>

      {/* Bet type badge */}
      <BetTypeBadge betType={pick.betType} />

      {/* Match + pick info */}
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontFamily: 'var(--font-display)',
          fontSize: 13,
          fontWeight: 700,
          letterSpacing: '0.03em',
          color: 'var(--text-primary)',
          textTransform: 'uppercase',
          marginBottom: 2,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {pick.pickLabel}
        </div>
        <div style={{
          fontFamily: 'var(--font-body)',
          fontSize: 11,
          color: 'var(--text-secondary)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          <span style={{ color: tourColor, fontWeight: 600 }}>{pick.tour}</span>
          {' · '}
          {pick.p1Name.split(' ').pop()} vs {pick.p2Name.split(' ').pop()}
          {pick.tournament && <> · {fmtTournament(pick.tournament, 20)}</>}
          {fmtTimeCT(pick.startUtc) && <span style={{ color: 'var(--text-muted)' }}> · {fmtTimeCT(pick.startUtc)}</span>}
        </div>
      </div>

      {/* Reasoning (truncated) */}
      <div style={{
        fontFamily: 'var(--font-body)',
        fontSize: 11,
        color: 'var(--text-secondary)',
        lineHeight: 1.4,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {pick.reasoning}
      </div>

      {/* Confidence */}
      <ConfidenceBadge confidence={pick.confidence} />

      {/* Edge */}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        fontWeight: 600,
        color: edgePositive ? 'var(--positive)' : 'var(--negative)',
        minWidth: 52,
        textAlign: 'right',
      }}>
        {edgePositive ? '+' : ''}{pick.edgePct.toFixed(1)}%
      </span>

      {/* EV + Kelly */}
      <div style={{ textAlign: 'right', minWidth: 64 }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          fontWeight: 700,
          color: 'var(--positive)',
        }}>
          {(pick.ev * 100).toFixed(1)}% EV
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--text-muted)',
        }}>
          {(pick.kellyFraction * 100).toFixed(1)}% stake (¼ Kelly)
        </div>
      </div>

      {/* Odds */}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        fontWeight: 700,
        color: pick.oddsAmerican != null && pick.oddsAmerican > 0 ? 'var(--positive)' : 'var(--text-secondary)',
        minWidth: 52,
        textAlign: 'right',
      }}>
        {fmtAmerican(pick.oddsAmerican)}
      </span>
    </div>
  )
}

function ParlayCard({ parlay }: { parlay: SuggestedParlay }) {
  const conf = CONF_STYLES[parlay.confidence] ?? CONF_STYLES.PASS
  const evPct = (parlay.combinedEv * 100).toFixed(1)
  const kellyPct = (parlay.combinedKelly * 100).toFixed(1)
  const edgePct = parlay.combinedEdgePct.toFixed(1)

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border-card)',
      borderRadius: 10,
      overflow: 'hidden',
      transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
    }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = withAlpha(conf.color, 0.314)
        e.currentTarget.style.boxShadow = `0 8px 32px rgba(0,0,0,0.45), 0 0 0 1px ${withAlpha(conf.color, 0.082)}`
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--border-card)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      {/* Top accent */}
      <div style={{
        height: 3,
        background: `linear-gradient(90deg, ${conf.color}, ${withAlpha(conf.color, 0.376)}, transparent)`,
      }} />

      {/* Header */}
      <div style={{
        padding: '14px 18px 10px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: conf.color,
          }}>
            VALUE PARLAY
          </span>
          <ConfidenceBadge confidence={parlay.confidence} />
        </div>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 14,
          fontWeight: 700,
          color: parlay.combinedOddsAmerican > 0 ? 'var(--positive)' : 'var(--text-secondary)',
        }}>
          {fmtAmerican(parlay.combinedOddsAmerican)}
        </span>
      </div>

      {/* Legs */}
      {parlay.legs.map((leg, i) => {
        const tourColor = TOUR_COLORS[leg.tour] ?? 'var(--text-secondary)'
        return (
          <div key={i} style={{
            padding: '10px 18px',
            borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--text-muted)',
              minWidth: 20,
            }}>
              L{i + 1}
            </span>
            <BetTypeBadge betType={leg.betType} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: '0.03em',
                color: 'var(--text-primary)',
                textTransform: 'uppercase',
              }}>
                {leg.pickLabel}
              </div>
              <div style={{
                fontFamily: 'var(--font-body)',
                fontSize: 11,
                color: 'var(--text-secondary)',
              }}>
                <span style={{ color: tourColor, fontWeight: 600 }}>{leg.tour}</span>
                {' · '}
                {leg.p1Name.split(' ').pop()} vs {leg.p2Name.split(' ').pop()}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-primary)',
              }}>
                {fmtPct(leg.ourProb)}
              </div>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--text-muted)',
              }}>
                {fmtAmerican(leg.oddsAmerican)}
              </div>
            </div>
          </div>
        )
      })}

      {/* Footer: combined stats */}
      <div style={{
        padding: '10px 18px 14px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 10,
      }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', rowGap: 8 }}>
          <StatPill label="Prob" value={fmtPct(parlay.combinedProb)} />
          <StatPill label="Edge" value={`${parlay.combinedEdgePct > 0 ? '+' : ''}${edgePct}%`} color={parlay.combinedEdgePct >= 0 ? 'var(--positive)' : 'var(--negative)'} />
          <StatPill label="EV" value={`${evPct}%`} color="var(--positive)" />
          <StatPill label="¼ Kelly" value={`${kellyPct}%`} />
        </div>
      </div>
    </div>
  )
}

function StatPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 8,
        fontWeight: 700,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--text-muted)',
        marginBottom: 2,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        fontWeight: 700,
        color: color ?? 'var(--text-primary)',
      }}>
        {value}
      </div>
    </div>
  )
}

// ── Mobile-friendly pick card (for narrow viewports) ────────────────────────

function SinglePickCard({ pick, rank }: { pick: BankrollPick; rank: number }) {
  const tourColor = TOUR_COLORS[pick.tour] ?? 'var(--text-secondary)'
  const edgePositive = pick.edgePct >= 0
  const conf = CONF_STYLES[pick.confidence] ?? CONF_STYLES.PASS

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border-card)',
      borderRadius: 10,
      overflow: 'hidden',
      transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
    }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = withAlpha(conf.color, 0.314)
        e.currentTarget.style.boxShadow = `0 8px 32px rgba(0,0,0,0.45), 0 0 0 1px ${withAlpha(conf.color, 0.082)}`
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--border-card)'
        e.currentTarget.style.boxShadow = 'none'
      }}
    >
      {/* Top accent */}
      <div style={{
        height: 3,
        background: `linear-gradient(90deg, ${conf.color}, ${withAlpha(conf.color, 0.376)}, transparent)`,
      }} />

      <div style={{ padding: '14px 16px' }}>
        {/* Row 1: Rank + bet type + pick label + confidence */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            fontWeight: 700,
            color: rank <= 3 ? 'var(--positive)' : 'var(--text-secondary)',
          }}>
            #{rank}
          </span>
          <BetTypeBadge betType={pick.betType} />
          <span style={{
            fontFamily: 'var(--font-display)',
            fontSize: 14,
            fontWeight: 700,
            letterSpacing: '0.03em',
            color: 'var(--text-primary)',
            textTransform: 'uppercase',
            flex: 1,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {pick.pickLabel}
          </span>
          <ConfidenceBadge confidence={pick.confidence} />
        </div>

        {/* Row 2: Match info */}
        <div style={{
          fontFamily: 'var(--font-body)',
          fontSize: 11,
          color: 'var(--text-secondary)',
          marginBottom: 8,
        }}>
          <span style={{ color: tourColor, fontWeight: 600 }}>{pick.tour}</span>
          {' · '}
          {pick.p1Name.split(' ').pop()} vs {pick.p2Name.split(' ').pop()}
          {pick.tournament && <> · {fmtTournament(pick.tournament, 25)}</>}
          {fmtTimeCT(pick.startUtc) && <span style={{ color: 'var(--text-muted)' }}> · {fmtTimeCT(pick.startUtc)}</span>}
        </div>

        {/* Row 3: Reasoning */}
        <div style={{
          fontFamily: 'var(--font-body)',
          fontSize: 11,
          color: 'var(--text-secondary)',
          lineHeight: 1.45,
          marginBottom: 10,
        }}>
          {pick.reasoning}
        </div>

        {/* Row 4: Stats bar */}
        <div style={{
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          flexWrap: 'wrap',
        }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 600,
            color: edgePositive ? 'var(--positive)' : 'var(--negative)',
          }}>
            Edge: {edgePositive ? '+' : ''}{pick.edgePct.toFixed(1)}%
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 700,
            color: 'var(--positive)',
          }}>
            {(pick.ev * 100).toFixed(1)}% EV
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--text-muted)',
          }}>
            {(pick.kellyFraction * 100).toFixed(1)}% stake (¼ Kelly)
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            fontWeight: 700,
            color: pick.oddsAmerican != null && pick.oddsAmerican > 0 ? 'var(--positive)' : 'var(--text-secondary)',
            marginLeft: 'auto',
          }}>
            {fmtAmerican(pick.oddsAmerican)}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Tour-grouped section ────────────────────────────────────────────────────

function TourSection({ title, color, singles, parlays, isNarrow }: {
  title: string
  color: string
  singles: BankrollPick[]
  parlays: SuggestedParlay[]
  isNarrow: boolean
}) {
  return (
    <div style={{ marginBottom: 40 }}>
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <div style={{ width: 3, height: 28, backgroundColor: color, borderRadius: 2, flexShrink: 0 }} />
        <span style={{
          fontFamily: 'var(--font-display)',
          fontSize: 22,
          fontWeight: 800,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--text-primary)',
        }}>
          {title}
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {singles.length > 0 && (
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--positive)',
              background: 'var(--positive-soft)',
              border: '1px solid color-mix(in srgb, var(--positive) 30%, transparent)',
              borderRadius: 4,
              padding: '2px 9px',
            }}>
              {singles.length} singles
            </span>
          )}
          {parlays.length > 0 && (
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--text-primary)',
              background: 'var(--bg-raised)',
              border: '1px solid var(--border-card)',
              borderRadius: 4,
              padding: '2px 9px',
            }}>
              {parlays.length} parlays
            </span>
          )}
        </div>
        <div style={{ flex: 1, height: 1, background: withAlpha(color, 0.145) }} />
      </div>

      {/* Singles */}
      {singles.length > 0 && (
        <div style={{ marginBottom: parlays.length > 0 ? 24 : 0 }}>
          {isNarrow ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {singles.map((pick, i) => (
                <SinglePickCard key={`${pick.matchId}-${pick.betType}-${pick.pickSide}-${i}`} pick={pick} rank={i + 1} />
              ))}
            </div>
          ) : (
            <div style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-card)',
              borderRadius: 10,
              overflow: 'hidden',
            }}>
              {/* Table header */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: SINGLES_COLS,
                gap: 12,
                padding: '10px 18px',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
              }}>
                {['#', 'Type', 'Pick', 'Reasoning', 'Conf', 'Edge', 'Value', 'Odds'].map((h) => (
                  <span key={h} style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    color: 'var(--text-muted)',
                    textAlign: h === '#' ? 'center' : h === 'Edge' || h === 'Value' || h === 'Odds' ? 'right' : 'left',
                  }}>
                    {h}
                  </span>
                ))}
              </div>

              {/* Rows */}
              {singles.map((pick, i) => (
                <SinglePickRow key={`${pick.matchId}-${pick.betType}-${pick.pickSide}-${i}`} pick={pick} rank={i + 1} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Parlays */}
      {parlays.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span style={{
              fontFamily: 'var(--font-display)',
              fontSize: 11,
              fontWeight: 800,
              letterSpacing: '0.14em',
              textTransform: 'uppercase',
              color: 'var(--text-primary)',
            }}>
              2-Leg Parlays
            </span>
            <div style={{ flex: 1, height: 1, background: 'var(--bg-raised)' }} />
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: 14,
          }}>
            {parlays.map((parlay, i) => (
              <ParlayCard key={i} parlay={parlay} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function ParlaysPage() {
  const isMobile = useIsMobile()
  const [tour, setTour] = useState<string | undefined>()
  const [customDate, setCustomDate] = useState<string | undefined>()

  const params = {
    ...(customDate ? { date: customDate } : {}),
    ...(tour ? { tour } : {}),
  }
  const { data, isLoading, isError, error, refetch } = useBankrollBuilder(
    Object.keys(params).length > 0 ? params : undefined,
  )

  return (
    <div className="page-shell">
      <div className="page-container is-wide">
      {/* Header */}
      <div className="page-head">
        <div>
          <div style={{
            fontFamily: 'var(--font-display)',
            fontSize: 11,
            letterSpacing: '0.2em',
            textTransform: 'uppercase',
            color: 'var(--text-secondary)',
            marginBottom: 6,
            fontWeight: 600,
          }}>
            Tennis · Value Engine
          </div>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontSize: isMobile ? 30 : 42,
            fontWeight: 800,
            letterSpacing: '0.03em',
            textTransform: 'uppercase',
            color: 'var(--text-primary)',
            margin: 0,
            lineHeight: 1.05,
          }}>
            Bankroll Builder
          </h1>
        </div>

        {data && (
          <div className="page-head__stats">
            <StatChip value={data.totalMatchesScanned} label="Scanned" />
            <StatChip value={data.singlesCount} label="Singles" color="var(--positive)" />
            <StatChip value={data.parlaysCount} label="Parlays" color="var(--text-primary)" />
          </div>
        )}
      </div>

      {/* Filters */}
      <>
        <div className="page-toolbar">
          <span style={{
            fontFamily: 'var(--font-body)',
            fontSize: 13,
            color: 'var(--text-secondary)',
          }}>
            Top singles &amp; 2-leg parlays ranked by edge, EV, and Kelly sizing
          </span>
          <div className="filter-bar-responsive" style={{ justifyContent: 'flex-end' }}>
            <Select
              style={{ width: isMobile ? '100%' : 130 }}
              placeholder="All Tours"
              allowClear
              value={tour}
              onChange={(v) => setTour(v || undefined)}
              options={[
                { value: 'ATP', label: 'ATP' },
                { value: 'WTA', label: 'WTA' },
              ]}
            />
            <DatePicker
              style={{ width: isMobile ? '100%' : 140 }}
              placeholder="Today"
              onChange={(_, dateStr) => setCustomDate(dateStr as string || undefined)}
              allowClear
            />
            <button
              onClick={() => refetch()}
              style={{
                padding: '6px 16px',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 6,
                background: 'var(--bg-raised)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                minHeight: 34,
              }}
            >
              Refresh
            </button>
          </div>
        </div>
      </>

      {/* Loading / Error */}
      {isLoading && <LoadingState />}
      {isError && <ErrorState error={error} onRetry={refetch} />}

      {data && (
        <>
          {/* ── Tour-grouped sections ── */}
          {(() => {
            const mainTours = ['ATP', 'WTA']
            const mainSingles = data.singles.filter(p => mainTours.includes(p.tour.toUpperCase()))
            const challSingles = data.singles.filter(p => !mainTours.includes(p.tour.toUpperCase()))
            const mainParlays = data.parlays.filter(p => p.legs.every(l => mainTours.includes(l.tour.toUpperCase())))
            const challParlays = data.parlays.filter(p => p.legs.some(l => !mainTours.includes(l.tour.toUpperCase())))

            return (
              <>
                {/* ── ATP & WTA ── */}
                {(mainSingles.length > 0 || mainParlays.length > 0) && (
                  <TourSection
                    title="ATP & WTA"
                    color="var(--text-primary)"
                    singles={mainSingles}
                    parlays={mainParlays}
                    isNarrow={isMobile}
                  />
                )}

                {/* ── Challengers / Other ── */}
                {(challSingles.length > 0 || challParlays.length > 0) && (
                  <TourSection
                    title="Challengers"
                    color="var(--challenger-teal)"
                    singles={challSingles}
                    parlays={challParlays}
                    isNarrow={isMobile}
                  />
                )}

                {/* Empty state */}
                {data.singles.length === 0 && data.parlays.length === 0 && (
                  <div style={{
                    textAlign: 'center',
                    padding: '60px 20px',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-body)',
                    fontSize: 14,
                  }}>
                    No value picks found for today. Check back closer to match time when odds are available.
                  </div>
                )}
              </>
            )
          })()}
        </>
      )}
      </div>
    </div>
  )
}
