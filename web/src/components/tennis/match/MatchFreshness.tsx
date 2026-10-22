import type { MatchDetail } from '~/types/tennis'
import { bookLabel } from '~/utils/matchOdds'
import { fmtSurface } from '~/utils/format'
import { researchDate, researchPair, researchTimestamp } from '~/utils/tennisResearch'

export default function MatchFreshness({ detail }: { detail: MatchDetail }) {
  const players = [detail.p1, detail.p2]
  const surface = researchPair(detail, false)
  const overall = researchPair(detail, true)
  const eloDates = players.map(player => detail.research?.players.find(item => item.playerId === player.playerId)?.eloAsOfDate)
  const odds = detail.research?.odds ?? []
  return <section className="tennis-research" aria-label="Data freshness">
    <h2>Data freshness</h2>
    <p className="tennis-research-note">TennisAbstract ratings and statistics. Rating dates describe the ratings; refresh times describe when rolling statistics were stored. Statistics cover the last 52 weeks and are current snapshots.</p>
    <div className="tennis-research-table-wrap"><table className="tennis-research-table" aria-label="Player data update dates">
      <thead><tr><th scope="col">Input</th>{players.map(player => <th scope="col" key={player.playerId}>{player.name}</th>)}</tr></thead>
      <tbody>
        <tr><th scope="row">ELO rating date</th>{eloDates.map((value, index) => <td key={players[index].playerId}>{researchDate(value)}</td>)}</tr>
        <tr><th scope="row">{detail.surface ? fmtSurface(detail.surface) : 'Surface'} stats refreshed</th>{surface.map((value, index) => <td key={players[index].playerId}>{researchTimestamp(value?.computedAt)}</td>)}</tr>
        <tr><th scope="row">Overall stats refreshed</th>{overall.map((value, index) => <td key={players[index].playerId}>{researchTimestamp(value?.computedAt)}</td>)}</tr>
      </tbody>
    </table></div>
    <dl className="tennis-research-timestamps">
      <div><dt>{detail.predictionSource === 'stored' ? 'Stored prediction generated' : detail.predictionSource === 'live' ? 'Live prediction generated' : 'Prediction generated'}</dt><dd>{researchTimestamp(detail.predictionGeneratedAt)}</dd></div>
      {odds.length > 0 ? odds.map(item => <div key={item.book}><dt>{bookLabel(item.book)} odds fetched</dt><dd>{researchTimestamp(item.fetchedAt)}</dd></div>)
        : <div><dt>Book odds fetched</dt><dd>Unavailable</dd></div>}
    </dl>
    <p className="tennis-research-note">Timestamps are Central Time (CT). Date-only ELO and workload records retain their source dates. Odds timestamps use the newest stored row per book{detail.startUtc ? ' before the scheduled start.' : '; no start time is available to establish a pre-match cutoff.'} Update times do not guarantee complete data coverage.</p>
  </section>
}
