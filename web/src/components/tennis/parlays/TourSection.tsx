import { withAlpha } from '~/utils/color'
import type { BankrollPick, SuggestedParlay } from '~/types/tennis'
import { ParlayCard } from '~/components/tennis/parlays/ParlayCard'
import { SinglePickCard } from '~/components/tennis/parlays/SinglePickCard'
import { SINGLES_COLS, SinglePickRow } from '~/components/tennis/parlays/SinglePickRow'

export function TourSection({ title, color, singles, parlays, isNarrow }: {
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
              color: 'var(--text-secondary)',
              background: 'var(--bg-raised)',
              border: '1px solid var(--bg-raised)',
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
                borderBottom: '1px solid var(--border-card)',
              }}>
                {['#', 'Type', 'Pick', 'Reasoning', 'Conf', 'Edge', 'Value', 'Odds'].map((h) => (
                  <span key={h} style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: 11,
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
