import { withAlpha } from '~/utils/color'
import { fmtSigned, fmtTimeCT, fmtTournament, tourColor } from '~/utils/format'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import type { BankrollPick } from '~/types/tennis'
import './parlays.css'
import { BetTypeBadge, ConfidenceBadge, TIER_STYLE } from '~/components/tennis/parlays/ParlayBadges'

export function SinglePickCard({ pick, rank }: { pick: BankrollPick; rank: number }) {
  const conf = TIER_STYLE

  return (
    <div className="parlay-card" style={{
      background: 'var(--bg-card)',
      borderRadius: 10,
      overflow: 'hidden',
    }}>
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
            color: 'var(--text-secondary)',
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
          <span style={{ color: tourColor(pick.tour), fontWeight: 600 }}>{pick.tour}</span>
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
            color: 'var(--text-primary)',
          }}>
            Edge: {fmtSigned(pick.edgePct, 1, '%')}
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            fontWeight: 700,
            color: 'var(--text-primary)',
          }}>
            {fmtPct(pick.ev)} EV
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--text-muted)',
          }}>
            {fmtPct(pick.kellyFraction)} stake (¼ Kelly)
          </span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            fontWeight: 700,
            color: 'var(--text-secondary)',
            marginLeft: 'auto',
          }}>
            {fmtAmerican(pick.oddsAmerican)}
          </span>
        </div>
      </div>
    </div>
  )
}
