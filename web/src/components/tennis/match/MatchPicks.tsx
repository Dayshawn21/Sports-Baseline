import type { BestPick, MatchDetail } from '~/types/tennis'
import { useMatchPicks } from '~/hooks/useMatchPicks'
import { canLoadMatchPicks, matchPickGroups } from '~/utils/tennisMatchBoard'
import { isFinished } from '~/utils/tennisMatch'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtEv } from '~/utils/tennisSlate'

function PickRows({ picks, bestBet }: { picks: BestPick[]; bestBet: boolean }) {
  return <ul className="tennis-match-picks">
    {picks.map((pick, index) => <li key={`${pick.pickType}-${pick.pick}-${index}`}>
      <div><small>{bestBet ? 'Best bet' : 'Angle'} · {pick.label}</small><strong>{pick.pick}</strong><p>{pick.reasoning}</p></div>
      <div className="tennis-match-picks__numbers">
        <span>{fmtAmerican(pick.oddsAmerican)} · Model {fmtPct(pick.modelProb)}</span>
        <span className={bestBet && (pick.evPct ?? 0) > 0 ? 'is-play' : undefined}>{fmtEv(pick.evPct)} EV</span>
        <span className="tennis-tier is-neutral">{pick.confidence}</span>
      </div>
    </li>)}
  </ul>
}

export default function MatchPicks({ detail }: { detail: MatchDetail }) {
  const query = useMatchPicks(detail)
  const { bestBets, angles } = matchPickGroups(detail, query.data?.matches ?? [])
  return <section className="tennis-match-card tennis-match-pick-section" aria-label="Match picks">
    <h2>Match picks</h2>
    {isFinished(detail) ? <p>Current match picks are unavailable after the match ends. Analysis shows the stored pre-match prediction when available.</p>
      : !canLoadMatchPicks(detail) ? <p>Match picks are unavailable until a start time is known.</p>
      : query.isLoading ? <p role="status">Loading match picks...</p>
      : query.isError ? <p role="alert">Match picks could not be loaded. <button className="tennis-prop-text-action" onClick={() => void query.refetch()}>Retry match picks</button></p>
      : bestBets.length + angles.length === 0 ? <p>No match picks meet the current display rules. Available prop lines are listed below.</p>
      : <><PickRows picks={bestBets} bestBet /><PickRows picks={angles} bestBet={false} /></>}
  </section>
}
