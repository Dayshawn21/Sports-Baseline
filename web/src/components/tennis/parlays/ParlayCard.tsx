import { withAlpha } from '~/utils/color'
import { fmtSigned, tourColor } from '~/utils/format'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import type { SuggestedParlay } from '~/types/tennis'
import './parlays.css'
import { BetTypeBadge, ConfidenceBadge, StatPill, TIER_STYLE } from '~/components/tennis/parlays/ParlayBadges'

export function ParlayCard({ parlay }: { parlay: SuggestedParlay }) {
  const conf = TIER_STYLE

  return (
    <div className="parlay-card" style={{
      background: 'var(--bg-card)',
      borderRadius: 10,
      overflow: 'hidden',
    }}>
      <div style={{
        height: 3,
        background: `linear-gradient(90deg, ${conf.color}, ${withAlpha(conf.color, 0.376)}, transparent)`,
      }} />

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
          color: 'var(--text-secondary)',
        }}>
          {fmtAmerican(parlay.combinedOddsAmerican)}
        </span>
      </div>

      {parlay.legs.map((leg, i) => {
        return (
          <div key={i} style={{
            padding: '10px 18px',
            borderTop: '1px solid var(--border-subtle)',
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
                <span style={{ color: tourColor(leg.tour), fontWeight: 600 }}>{leg.tour}</span>
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

      <div style={{
        padding: '10px 18px 14px',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 10,
      }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap', rowGap: 8 }}>
          <StatPill label="Prob" value={fmtPct(parlay.combinedProb)} />
          <StatPill label="Edge" value={fmtSigned(parlay.combinedEdgePct, 1, '%')} color="var(--text-primary)" />
          <StatPill label="EV" value={fmtPct(parlay.combinedEv)} color="var(--text-primary)" />
          <StatPill label="¼ Kelly" value={fmtPct(parlay.combinedKelly)} />
        </div>
      </div>
    </div>
  )
}
