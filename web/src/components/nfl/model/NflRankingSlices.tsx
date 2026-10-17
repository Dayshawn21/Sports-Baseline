import type { CSSProperties } from 'react'
import type { PropRankingRecord, PropRankingSlice } from '~/types/propRanking'
import { sliceLabel, sliceProgress, verdictLabel } from '~/utils/nflTrackRecord'
import { signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

function SliceCard({ slice, rule }: { slice: PropRankingSlice, rule: PropRankingRecord['rule'] }) {
  const progress = { '--w': `${sliceProgress(slice.n, slice.weeks, rule.minPicks, rule.minWeeks) * 100}%` } as CSSProperties
  const tone = signalClass(slice.signal)
  return (
    <section className="nfl-model-card nfl-model-slice" aria-label={sliceLabel(slice.oddsType, slice.side)}>
      <div className="nfl-model-slice__top">
        <span className="nfl-model-label">{sliceLabel(slice.oddsType, slice.side)}</span>
        <span className={`nfl-model-tag ${tone}`}>{verdictLabel(slice.verdict)}</span>
      </div>
      <div className="nfl-model-progress" style={progress}><i /></div>
      <dl className="nfl-model-kv">
        <div><dt>Picks</dt><dd>{slice.n} of {rule.minPicks}</dd></div>
        <div><dt>Weeks</dt><dd>{slice.weeks} of {rule.minWeeks}+</dd></div>
        <div>
          <dt>Hit rate</dt>
          <dd className={tone}>
            {slice.hitRate === null ? 'No picks yet' : pct(slice.hitRate)}
            {slice.standardError !== null && <> &plusmn; {(slice.standardError * 100).toFixed(1)}</>}
          </dd>
        </div>
        <div><dt>Break-even</dt><dd>{pct(slice.breakEven)}</dd></div>
      </dl>
    </section>
  )
}

export default function NflRankingSlices({ data }: { data: PropRankingRecord }) {
  const { funnel, rule } = data
  const frozenWeeks = data.coverage.filter((week) => week.frozen > 0)
  return <>
    <div className="nfl-model-slices">
      {data.slices.map((slice) => <SliceCard key={`${slice.oddsType}-${slice.side}`} slice={slice} rule={rule} />)}
    </div>
    <p className="nfl-model-note">
      {data.frozenRows.toLocaleString()} frozen rows on completed games
      {frozenWeeks.length > 0 && <>, frozen on{' '}
        {frozenWeeks.map((week) => `week ${week.week} (${week.frozen.toLocaleString()} of ${week.lines.toLocaleString()} lines)`).join(', ')}
      </>}. {funnel.calls.toLocaleString()} settled calls, {funnel.withPOver.toLocaleString()} with a P(over),{' '}
      {funnel.picks} clear break-even by {Math.round(rule.minPickMargin * 100)} points, {funnel.bets} after one pick per bet.
    </p>
    <p className="nfl-model-note">
      A slice adopts only when its fixed sample (the first whole weeks holding {rule.minPicks} picks over{' '}
      {rule.minWeeks}+ weeks) hits break-even plus 2 SE. A reject is final for {data.modelVersion} and{' '}
      {data.overProbabilityVersion}. Rates stay gray until then; the error bar is the binomial SE after goblin and demon
      ladders collapse to one pick per bet.
    </p>
  </>
}
