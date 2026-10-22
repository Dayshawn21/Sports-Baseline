import type { MatchDetail, MatchWorkload } from '~/types/tennis'
import { researchDate, workloadSets } from '~/utils/tennisResearch'

const ROWS: Array<[string, (value: MatchWorkload | undefined) => string]> = [
  ['Seven-day window (end excluded)', value => value ? `${researchDate(value.windowStart)} to ${researchDate(value.windowEndExclusive)}` : 'Unavailable'],
  ['Previous recorded match', value => value?.previousMatchDate ? researchDate(value.previousMatchDate) : value ? 'Not found in stored history' : 'Unavailable'],
  ['Calendar days since match', value => value?.calendarDaysSinceMatch == null ? 'Unavailable' : String(value.calendarDaysSinceMatch)],
  ['Recorded matches in window', value => value ? String(value.matchesPlayed) : 'Unavailable'],
  ['Completed sets in window', workloadSets],
  ['Score coverage', value => value ? `${value.matchesWithCompleteScores} of ${value.matchesPlayed} recorded matches` : 'Unavailable'],
  ['Minutes played', value => value?.minutesPlayed == null ? 'Unavailable' : `${value.minutesPlayed} min`],
]

export default function MatchWorkloadContext({ detail }: { detail: MatchDetail }) {
  const players = [detail.p1, detail.p2]
  const workload = players.map(player => detail.research?.players.find(item => item.playerId === player.playerId)?.workload)
  return <section className="tennis-research" aria-label="Recent workload">
    <h2>Recent workload</h2>
    <p className="tennis-research-note">Seven days before this match, using UTC match dates. Same-day matches are excluded because reliable completion times are unavailable.</p>
    <div className="tennis-research-table-wrap"><table className="tennis-research-table" aria-label="Pre-match workload comparison">
      <thead><tr><th scope="col">Metric</th>{players.map(player => <th scope="col" key={player.playerId}>{player.name}</th>)}</tr></thead>
      <tbody>{ROWS.map(([label, format]) => <tr key={label}><th scope="row">{label}</th>
        {workload.map((value, index) => <td key={players[index].playerId}>{format(value)}</td>)}
      </tr>)}</tbody>
    </table></div>
    <p className="tennis-research-note">Based on the match history stored in Lineform; coverage may be incomplete. The previous-match lookup covers up to 365 days. Calendar days are not hours of recovery.</p>
    <p className="tennis-research-note">Set totals include only completed sets we can read from stored scores. Partial or missing scores produce a lower bound or an unavailable total. Match duration is not stored, so minutes are unavailable.</p>
  </section>
}
