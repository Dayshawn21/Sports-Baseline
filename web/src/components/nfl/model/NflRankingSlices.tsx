import type { CSSProperties } from 'react'
import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import { rankingPresentation, rankingSliceStatus, sliceLabel, sliceProgress } from '~/utils/nflTrackRecord'
import { signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

function SliceCard({ slice, rule, referenceOnly }: {
  slice: PropRankingSlice, rule: PropRankingRecord['rule'], referenceOnly: boolean,
}) {
  const progress = { '--w': `${sliceProgress(slice.n, slice.weeks, rule.minPicks, rule.minWeeks) * 100}%` } as CSSProperties
  const status = rankingSliceStatus(slice, referenceOnly)
  const tone = signalClass(status.signal)
  return (
    <section className="nfl-model-card nfl-model-slice" aria-label={sliceLabel(slice.oddsType, slice.side)}>
      <div className="nfl-model-slice__top">
        <span className="nfl-model-label">{sliceLabel(slice.oddsType, slice.side)}</span>
        <span className={`nfl-model-tag ${tone}`}>{status.label}</span>
      </div>
      <div className="nfl-model-progress" style={progress}><i /></div>
      <dl className="nfl-model-kv">
        <div><dt>Picks</dt><dd>{slice.n} of {rule.minPicks}</dd></div>
        <div><dt>Weeks</dt><dd>{slice.weeks} of {rule.minWeeks}+</dd></div>
        <div>
          <dt>Hit rate</dt>
          <dd className={tone}>
            {slice.hitRate === null ? status.noPicks : pct(slice.hitRate)}
            {slice.standardError !== null && <> &plusmn; {(slice.standardError * 100).toFixed(1)}</>}
          </dd>
        </div>
        <div><dt>Break-even</dt><dd>{pct(slice.breakEven)}</dd></div>
      </dl>
    </section>
  )
}

export default function NflRankingSlices({ data, referenceOnly = false }: {
  data: PropRankingRecord<string | null>, referenceOnly?: boolean,
}) {
  const { funnel, rule } = data
  const view = rankingPresentation(data, referenceOnly)
  const frozenWeeks = referenceOnly ? data.coverage : data.coverage.filter((week) => week.frozen > 0)
  return <>
    {referenceOnly && <p className="nfl-model-note nfl-model-reference">
      Rec Targets is a reference projection. P(over) is unavailable because validation did not pass,
      so these lines cannot accrue probability-based picks. Goblin and demon lines are not projected.
    </p>}
    {referenceOnly && view.empty && <p className="model-section-empty">
      No frozen Rec Targets predictions on completed games yet. Predictions are graded after the games
      and their weekly stats are complete.
    </p>}
    <div className="nfl-model-slices">
      {view.slices.map((slice) => <SliceCard key={`${slice.oddsType}-${slice.side}`} slice={slice} rule={rule} referenceOnly={referenceOnly} />)}
    </div>
    <p className="nfl-model-note">
      {data.frozenRows.toLocaleString()} frozen rows on completed games
      {frozenWeeks.length > 0 && <>{referenceOnly ? ', coverage: ' : ', frozen on '}
        {frozenWeeks.map((week) => `week ${week.week} (${week.frozen.toLocaleString()} of ${week.lines.toLocaleString()} ${referenceOnly ? 'eligible props frozen' : 'lines'})`).join(', ')}
      </>}. {funnel.calls.toLocaleString()} settled calls, {funnel.withPOver.toLocaleString()} with a P(over),{' '}
      {funnel.picks} clear break-even by {Math.round(rule.minPickMargin * 100)} points, {funnel.bets} after one pick per bet.
    </p>
    {!referenceOnly && <p className="nfl-model-note">
      A slice adopts only when its fixed sample (the first whole weeks holding {rule.minPicks} picks over{' '}
      {rule.minWeeks}+ weeks) hits break-even plus 2 SE. A reject is final for {data.modelVersion} and{' '}
      {view.probabilityVersion}. Rates stay gray until then; the error bar is the binomial SE after goblin and demon
      ladders collapse to one pick per bet.
    </p>}
  </>
}
