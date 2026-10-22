import { useState } from 'react'
import type { MatchDetail, MatchResearchStats } from '~/types/tennis'
import { fmtPct } from '~/utils/odds'
import { fmtSurface } from '~/utils/format'
import { isFinished } from '~/utils/tennisMatch'
import { researchPair } from '~/utils/tennisResearch'

type Metric = [label: string, key: keyof Pick<MatchResearchStats,
  'winRate' | 'holdPct' | 'returnPointsWon' | 'breakConversionPct' | 'firstInPct' |
  'firstServeWon' | 'secondServeWon' | 'firstReturnWon' | 'secondReturnWon'>]

const SURFACE_ROWS: Metric[] = [
  ['Match win rate', 'winRate'], ['Service games held', 'holdPct'],
  ['Return points won', 'returnPointsWon'], ['Break points converted', 'breakConversionPct'],
]
const SERVE_ROWS: Metric[] = [
  ['First serves in', 'firstInPct'], ['First-serve points won', 'firstServeWon'],
  ['Second-serve points won', 'secondServeWon'],
]
const RETURN_ROWS: Metric[] = [
  ['First-serve return points won', 'firstReturnWon'], ['Second-serve return points won', 'secondReturnWon'],
]

function Rates({ rows, stats }: { rows: Metric[]; stats: [MatchResearchStats | null, MatchResearchStats | null] }) {
  return <>{rows.map(([label, key]) => <tr key={key}>
    <th scope="row">{label}</th>
    {stats.map((item, index) => <td key={index}>{fmtPct(item?.[key], 1)}</td>)}
  </tr>)}</>
}

function Samples({ stats, names }: { stats: [MatchResearchStats | null, MatchResearchStats | null]; names: string[] }) {
  return <div className="tennis-research-samples">
    {stats.map((item, index) => <p key={names[index]}>
      <strong>{names[index]}</strong>{' '}
      {item == null ? 'Stats unavailable for this scope.'
        : item.matchesCount == null ? 'Sample size unavailable.'
        : <>{item.matchesCount} matches{item.thinSample ? ' · Thin sample: fewer than 10 matches.' : ''}</>}
    </p>)}
  </div>
}

function PlayerColumns({ detail }: { detail: MatchDetail }) {
  return <thead><tr><th scope="col">Metric</th><th scope="col">{detail.p1.name}</th><th scope="col">{detail.p2.name}</th></tr></thead>
}

export default function MatchSurfaceContext({ detail }: { detail: MatchDetail }) {
  const [overall, setOverall] = useState(false)
  const stats = researchPair(detail, overall)
  const names = [detail.p1.name, detail.p2.name]
  const scope = overall ? 'All surfaces' : detail.surface ? fmtSurface(detail.surface) : 'Surface unknown'
  return <section className="tennis-research" aria-label="Surface and serve comparisons">
    <div className="tennis-research-heading"><h2>Surface &amp; serve comparison</h2>
      <div className="tennis-research-scope" role="group" aria-label="Statistics scope">
        <button type="button" aria-pressed={!overall} onClick={() => setOverall(false)}>{detail.surface ? fmtSurface(detail.surface) : 'Match surface'}</button>
        <button type="button" aria-pressed={overall} onClick={() => setOverall(true)}>All surfaces</button>
      </div>
    </div>
    <p className="tennis-research-note">{scope} · Last 52 weeks · TennisAbstract · Current rolling snapshot.</p>
    {detail.indoor && !overall && <p className="tennis-research-note">Includes indoor and outdoor matches on this surface.</p>}
    {isFinished(detail) && <p className="tennis-research-note">These are current statistics, not the stats available before this finished match.</p>}
    <Samples stats={stats} names={names} />
    <div className="tennis-research-table-wrap"><table className="tennis-research-table" aria-label={`${scope} surface statistics`}>
      <PlayerColumns detail={detail} /><tbody><Rates rows={SURFACE_ROWS} stats={stats} /></tbody>
    </table></div>
    <p className="tennis-research-note">Break points converted measures conversion of break-point chances, not return games won. A dash indicates unavailable data.</p>
    <h3>Serve versus return</h3>
    <p className="tennis-research-note">Read each player's serve numbers against the other player's return numbers. These historical rates describe the matchup; they are not a new projection.</p>
    <div className="tennis-research-table-wrap"><table className="tennis-research-table" aria-label={`${scope} serve and return statistics`}>
      <PlayerColumns detail={detail} />
      <tbody>
        <Rates rows={SERVE_ROWS} stats={stats} />
        <Rates rows={RETURN_ROWS} stats={stats} />
      </tbody>
    </table></div>
    <p className="tennis-research-note">First serves in is per service point; serve points won is per first- or second-serve point. Return points won is one minus the corresponding serve-points-won rate allowed to opponents. The same {scope.toLowerCase()} match samples apply to both tables; point-count denominators are unavailable.</p>
  </section>
}
