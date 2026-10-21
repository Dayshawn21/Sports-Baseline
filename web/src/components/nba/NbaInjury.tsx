import type { NbaInjury, NbaInjuryReport } from '~/types/nba'
import { nbaInjuryFreshness, nbaInjuryTime } from '~/utils/nbaInjuries'
import './nba-injury.css'

interface TagProps {
  injury: NbaInjury | null
  freshness: NbaInjuryReport['freshness']
}

export function NbaInjuryTag({ injury, freshness }: TagProps) {
  if (!injury || freshness === 'unavailable') return null
  return <span className="nba-injury-tag">{injury.status}{freshness === 'stale' ? ' (stale)' : ''}</span>
}

interface EvidenceProps {
  injury: NbaInjury | null
  report: NbaInjuryReport
  startUtc: string | null
  now: Date
}

export function NbaInjuryEvidence({ injury, report, startUtc, now }: EvidenceProps) {
  const freshness = nbaInjuryFreshness(report, startUtc, now)
  const preTip = startUtc !== null && Date.parse(startUtc) <= now.getTime()
  return <section className="nba-prop-evidence__section nba-injury-evidence" aria-label="Injury report">
    <h4>Injury report</h4>
    {freshness === 'unavailable' ? <p>Injury report unavailable.</p> : <>
      {injury ? <>
        <NbaInjuryTag injury={injury} freshness={freshness} />
        <p>{injury.detail ?? 'No injury detail provided by ESPN.'}</p>
        {injury.returnDate && <p>Expected return (ESPN): {injury.returnDate}</p>}
      </> : <p>No injury reported by ESPN for this player.</p>}
      {freshness === 'stale' && <p>Stale report. Last available ESPN snapshot.</p>}
      <dl className="nba-injury-evidence__times">
        <div><dt>{preTip ? 'ESPN pre-tip snapshot' : 'ESPN snapshot'}</dt><dd><time dateTime={report.fetchedAt ?? undefined}>{nbaInjuryTime(report.fetchedAt)}</time></dd></div>
        {injury?.sourceUpdatedAt && <div><dt>ESPN entry updated</dt><dd><time dateTime={injury.sourceUpdatedAt}>{nbaInjuryTime(injury.sourceUpdatedAt)}</time></dd></div>}
      </dl>
    </>}
    <p>Display context only.</p>
  </section>
}
