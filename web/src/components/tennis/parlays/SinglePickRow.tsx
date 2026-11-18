import { fmtSigned, fmtTimeCT, fmtTournament, tourColor } from '~/utils/format'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import type { BankrollPick } from '~/types/tennis'
import './parlays.css'
import { BetTypeBadge, ConfidenceBadge } from '~/components/tennis/parlays/ParlayBadges'

/** Column template for the singles table — the row adds a trailing action column. */
export const SINGLES_COLS = '32px 60px minmax(200px, 0.85fr) minmax(240px, 1.6fr) auto auto auto auto'

export function SinglePickRow({ pick, rank }: { pick: BankrollPick; rank: number }) {

  return (
    <div
      className="parlay-single-row"
      style={{
        display: 'grid',
        gridTemplateColumns: SINGLES_COLS,
        gap: 12,
        alignItems: 'center',
        padding: '12px 18px',
        borderBottom: '1px solid var(--border-subtle)',
        transition: 'background 0.12s ease',
      }}
    >
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 14,
        fontWeight: 700,
        color: 'var(--text-secondary)',
        textAlign: 'center',
      }}>
        #{rank}
      </span>

      <BetTypeBadge betType={pick.betType} />

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
          <span style={{ color: tourColor(pick.tour), fontWeight: 600 }}>{pick.tour}</span>
          {' · '}
          {pick.p1Name.split(' ').pop()} vs {pick.p2Name.split(' ').pop()}
          {pick.tournament && <> · {fmtTournament(pick.tournament, 20)}</>}
          {fmtTimeCT(pick.startUtc) && <span style={{ color: 'var(--text-muted)' }}> · {fmtTimeCT(pick.startUtc)}</span>}
        </div>
      </div>

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

      <ConfidenceBadge confidence={pick.confidence} />

      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        fontWeight: 600,
        color: 'var(--text-primary)',
        minWidth: 52,
        textAlign: 'right',
      }}>
        {fmtSigned(pick.edgePct, 1, '%')}
      </span>

      <div style={{ textAlign: 'right', minWidth: 64 }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 12,
          fontWeight: 700,
          color: 'var(--text-primary)',
        }}>
          {fmtPct(pick.ev)} EV
        </div>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 11,
          color: 'var(--text-muted)',
        }}>
          {fmtPct(pick.kellyFraction)} stake (¼ Kelly)
        </div>
      </div>

      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        fontWeight: 700,
        color: 'var(--text-secondary)',
        minWidth: 52,
        textAlign: 'right',
      }}>
        {fmtAmerican(pick.oddsAmerican)}
      </span>
    </div>
  )
}
