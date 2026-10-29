import { usePrizePicksPropsAudit } from '~/hooks/useProps'

/**
 * Data-health readout for the PrizePicks props pipeline.
 *
 * Props are linked to matches upstream, and an unlinked prop also loses its
 * side — which the opportunity board can only report as an absence. This
 * banner names the actual failure counts, so a broken link step is visible as a
 * broken link step rather than as "no picks today".
 */
export default function PropsAuditBanner() {
  const query = usePrizePicksPropsAudit()
  const summary = query.data?.summary

  if (query.isLoading) return null
  if (query.isError) {
    return (
      <div className="props-audit props-audit--issues">
        <div>
          <div className="props-audit__title">PrizePicks Data Audit</div>
          <div className="props-audit__subtitle">Audit could not be loaded.</div>
        </div>
        <button type="button" className="props-audit__retry" onClick={() => query.refetch()}>
          Retry
        </button>
      </div>
    )
  }
  if (!summary) return null

  const items: Array<[string, number]> = [
    ['Players', summary.unresolvedPlayerCount],
    ['Matches', summary.unlinkedMatchCount],
    ['Stats', summary.missingStatsCount],
    ['Stale', summary.staleStatsCount],
    ['Model gaps', summary.unsupportedStatCount],
    ['Predictions', summary.missingPredictionCount],
    ['Small sample', summary.smallSampleCount],
  ]
  const issues = items.filter(([, count]) => count > 0)
  const issueCount = issues.reduce((total, [, count]) => total + count, 0)

  return (
    <div className={`props-audit ${issueCount ? 'props-audit--issues' : 'props-audit--clean'}`}>
      <div>
        <div className="props-audit__title">PrizePicks Data Audit</div>
        <div className="props-audit__subtitle">
          {summary.totalProps.toLocaleString()} props checked
          {issueCount
            ? ` · ${issueCount.toLocaleString()} data warnings`
            : ' · data links look clean'}
        </div>
      </div>
      {issues.length > 0 && (
        <div className="props-audit__chips">
          {issues.map(([label, count]) => (
            <span key={label} className="props-audit__chip">{label}: {count.toLocaleString()}</span>
          ))}
        </div>
      )}
    </div>
  )
}
