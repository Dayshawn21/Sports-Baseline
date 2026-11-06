import { fmtEv } from '~/utils/tennisSlate'
import type { PropLine } from '~/types/tennis'
import type { UnifiedTennisMatch } from '~/utils/unifiedTennis'
import { fmtStartCT } from '~/utils/format'
import { payoutTier } from '~/utils/tennisPropBoard'
import { decisionOverPct } from '~/utils/tennisPropCards'
import './tennis-match-detail.css'

const MISSING = '--'

/** Projection, gap and P(over) against the payout's break-even, gray unless 48e adopted its slice (48f, 48g). */
function PropItem({ prop }: { prop: PropLine }) {
  const line = prop.line == null ? null : Number(prop.line)
  const payout = payoutTier(prop)
  const pOver = decisionOverPct(prop)
  const gap = line != null && prop.statAvg != null ? ` (${prop.statAvg - line >= 0 ? '+' : ''}${(prop.statAvg - line).toFixed(1)})` : ''
  const cells = [
    `Model ${prop.statAvg == null ? MISSING : prop.statAvg.toFixed(1)}${gap}`,
    `P(over) ${pOver == null ? MISSING : `${pOver.toFixed(0)}%`} vs ${prop.breakEvenPct == null ? MISSING : `${prop.breakEvenPct.toFixed(1)}%`} BE`,
    `${prop.matchesCount ?? MISSING} match sample`,
  ]
  return (
    <div className="tennis-detail__pick">
      <strong>{prop.playerName} · {prop.statType}</strong>
      <small>Line {line == null ? MISSING : line.toFixed(1)}{payout ? ` · ${payout}` : ''}</small>
      <div className="tennis-detail__cells">
        {cells.map((cell, index) => <span key={index}>{cell}</span>)}
        {prop.adoptedPick && (
          <span className="tennis-detail__adopted">
            {prop.adoptedPick.side.toUpperCase()} +{(prop.adoptedPick.margin * 100).toFixed(1)} pts vs BE
          </span>
        )}
        <span className="tennis-detail__ev">{fmtEv(prop.evPct)}</span>
      </div>
    </div>
  )
}

/**
 * An unlinked prop group's detail under its slate row, in board order. Predicted matches
 * open their analysis page instead, so this never has best bets or match facts (F-41, F-43).
 */
export default function TennisMatchDetail({ match }: { match: UnifiedTennisMatch }) {
  const start = fmtStartCT(match.props[0]?.startTime) || 'Time TBA'
  return (
    <>
      <header className="tennis-detail__context">
        <span className="tennis-detail__where">Player props · {start}</span>
      </header>
      <section className="tennis-detail__section">
        <h3 className="tennis-detail__label">Props <span>{match.props.length}</span></h3>
        {match.props.map((prop) => <PropItem key={prop.id} prop={prop} />)}
      </section>
    </>
  )
}
