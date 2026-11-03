import type { CSSProperties } from 'react'
import type { NflModelRanking } from '~/types/nfl'
import { sliceProgress } from '~/utils/nflTrackRecord'
import {
  logLossRows, notFrozenNote, sliceLogLossText, VOLUME_COVERAGE_LABEL, VOLUME_LOG_LOSS_NOTE, VOLUME_NOTE, volumeSlices,
  type VolumeSliceView,
} from '~/utils/nflVolumeRecord'
import { signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

function SliceCard({ view, rule }: { view: VolumeSliceView, rule: NflModelRanking['rule'] }) {
  const { slice } = view
  const logLoss = sliceLogLossText(view)
  const progress = { '--w': `${view.frozen ? sliceProgress(slice.n, slice.weeks, rule.minPicks, rule.minWeeks) * 100 : 0}%` } as CSSProperties
  return (
    <section className="nfl-model-card nfl-model-slice" aria-label={view.label}>
      <div className="nfl-model-slice__top">
        <span className="nfl-model-label">{view.label}</span>
        <span className={`nfl-model-tag ${signalClass('neutral')}`}>{view.status}</span>
      </div>
      <div className="nfl-model-progress" style={progress}><i /></div>
      {view.frozen
        ? <dl className="nfl-model-kv">
          <div><dt>Picks</dt><dd>{slice.n} of {rule.minPicks}</dd></div>
          <div><dt>Weeks</dt><dd>{slice.weeks} of {rule.minWeeks}+</dd></div>
          <div><dt>Hit rate</dt><dd>{slice.hitRate === null ? 'No picks yet' : pct(slice.hitRate)}</dd></div>
          <div><dt>Break-even</dt><dd>{pct(slice.breakEven)}</dd></div>
          {logLoss !== null && <div><dt>Log loss</dt><dd>{logLoss}</dd></div>}
        </dl>
        : <p className="nfl-model-note">No frozen sample for this payout yet.</p>}
    </section>
  )
}

/** The volume model's forward record: gray progress only, never a pick, a rank or a color until a verdict exists. */
export default function NflVolumeRecord({ data }: { data: NflModelRanking }) {
  const views = volumeSlices(data)
  const weeks = data.coverage.filter((week) => week.lines > 0)
  const rows = logLossRows(data.logLoss?.progress)
  return <>
    <p className="nfl-model-note nfl-model-reference">{VOLUME_NOTE}</p>
    {data.frozenRows === 0 && <p className="model-section-empty">
      No frozen volume predictions on completed games yet. Predictions are graded after the games and their weekly stats are complete.
    </p>}
    <div className="nfl-model-slices">
      {views.map((view) => <SliceCard key={view.key} view={view} rule={data.rule} />)}
    </div>
    <section className="nfl-model-card nfl-model-slice nfl-model-volume-loss" aria-label="Log-loss progress">
      <div className="nfl-model-slice__top"><span className="nfl-model-label">Log-loss progress</span></div>
      <dl className="nfl-model-kv">
        {rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}
      </dl>
    </section>
    <p className="nfl-model-note">
      {data.frozenRows.toLocaleString()} frozen rows on completed games
      {weeks.length > 0 && <>, {VOLUME_COVERAGE_LABEL}: {weeks.map((week) => `week ${week.week} (${week.frozen.toLocaleString()} of ${week.lines.toLocaleString()} eligible props frozen)`).join(', ')}</>}.
      {' '}{data.funnel.calls.toLocaleString()} settled calls, {data.funnel.picks} clear break-even by {Math.round(data.rule.minPickMargin * 100)} points.
    </p>
    <p className="nfl-model-note">{VOLUME_LOG_LOSS_NOTE} {notFrozenNote(views)}</p>
  </>
}
