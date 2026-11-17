import { withAlpha } from '~/utils/color'

const BET_TYPE_CONFIG: Record<string, { label: string; color: string; short: string }> = {
  ml:           { label: 'Moneyline',     color: 'var(--text-secondary)', short: 'ML' },
  '2-0':        { label: 'Straight Sets', color: 'var(--text-secondary)', short: '2-0' },
  '3-0':        { label: 'Straight Sets', color: 'var(--text-secondary)', short: '3-0' },
  underdog_set: { label: 'Underdog Set',  color: 'var(--text-secondary)', short: 'U-SET' },
  total_games:  { label: 'Total Games',   color: 'var(--caution)', short: 'TOTAL' },
}

// One muted style for every tier: no tennis tier has passed the 32b tier rule (F-21).
export const TIER_STYLE = { color: 'var(--text-muted)', bg: 'var(--bg-raised)', border: 'var(--bg-raised)' }

export function BetTypeBadge({ betType }: { betType: string }) {
  const cfg = BET_TYPE_CONFIG[betType] ?? { label: betType, color: 'var(--text-muted)', short: betType.slice(0, 3).toUpperCase() }
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: 11,
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

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  const s = TIER_STYLE
  return (
    <span style={{
      fontFamily: 'var(--font-display)',
      fontSize: 11,
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

export function StatPill({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        fontFamily: 'var(--font-display)',
        fontSize: 11,
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
