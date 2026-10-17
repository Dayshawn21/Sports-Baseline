import type { MatchDetail } from '~/types/tennis'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtStartCT } from '~/utils/format'
import { fmtEv } from '~/utils/tennisSlate'
import { heroSide, isFinished, sideView } from '~/utils/tennisMatch'

function lastName(name: string): string {
  return name.split(/\s+/).filter(Boolean).pop() ?? name
}

export default function MatchHero({ detail }: { detail: MatchDetail }) {
  if (!detail.prediction) {
    return (
      <div className="tennis-match-empty">
        {isFinished(detail)
          ? 'No pre-match prediction was stored for this match, so there is nothing to grade it against.'
          : 'No prediction for this match yet. A player may be missing the data the model needs.'}
      </div>
    )
  }

  const view = sideView(detail, heroSide(detail))
  const pick = detail.mlPick
  // Green follows the slate: only a best-bet moneyline with positive EV.
  const isPlay = pick != null && (pick.evPct ?? 0) > 0
  const modelSub = detail.predictionSource === 'stored'
    ? `pre-match · ${fmtStartCT(detail.predictionGeneratedAt)}`
    : 'ensemble'
  const noPlayReason = view.odds == null ? 'no stored price' : 'no moneyline play'

  return (
    <div className="tennis-match-hero">
      <div className="tennis-match-tile">
        <div className="tennis-match-tile__label">{lastName(view.name)} to win · model</div>
        <div className="tennis-match-tile__value">{fmtPct(view.modelProb)}</div>
        <div className="tennis-match-tile__sub">{modelSub}</div>
      </div>
      <div className="tennis-match-tile">
        <div className="tennis-match-tile__label">Market · de-vigged</div>
        <div className="tennis-match-tile__value is-muted">{fmtPct(view.marketProb)}</div>
        <div className="tennis-match-tile__sub">{view.odds == null ? 'no stored price' : `priced ${fmtAmerican(view.odds)}`}</div>
      </div>
      <div className="tennis-match-tile">
        <div className="tennis-match-tile__label">Moneyline EV</div>
        <div className={`tennis-match-tile__value${isPlay ? ' is-play' : ' is-muted'}`}>{pick ? fmtEv(pick.evPct) : '—'}</div>
        <div className="tennis-match-tile__sub">
          {pick
            ? <>{pick.pick} · <span className={`tennis-tier is-${pick.confidence.toLowerCase()}`}>{pick.confidence}</span> · edge {fmtEv(pick.edgePct)}</>
            : noPlayReason}
        </div>
      </div>
    </div>
  )
}
