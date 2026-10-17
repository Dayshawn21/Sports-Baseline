import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { useModelPredictions, useModelPrizePicksLines, useModelPropTiers } from '~/hooks/useModelTrackRecord'
import { ensembleVerdictText, seMultiple, signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

interface CardProps<T> {
  label: string
  query: UseQueryResult<T>
  render: (data: T) => { value: string, valueClass?: string, say: ReactNode }
}

function VerdictCard<T>({ label, query, render }: CardProps<T>) {
  const body = query.data ? render(query.data) : null
  const fallback = query.isLoading ? 'Grading...' : 'Unavailable'
  return (
    <div className="tennis-model-card tennis-model-verdict">
      <div className="tennis-model-verdict__label">{label}</div>
      <div className={`tennis-model-verdict__value ${body?.valueClass ?? (body ? '' : 'is-dim')}`}>{body?.value ?? fallback}</div>
      {body && <div className="tennis-model-verdict__say">{body.say}</div>}
    </div>
  )
}

export default function ModelVerdictCards({ modelVersion }: { modelVersion?: string }) {
  const predictions = useModelPredictions(modelVersion)
  const lines = useModelPrizePicksLines()
  const tiers = useModelPropTiers()

  return (
    <section className="tennis-model-verdicts" aria-label="Headline verdicts">
      <VerdictCard label="Ensemble vs market" query={predictions} render={(data) => {
        const pooled = data.groups.find((g) => g.group === 'ATP+WTA')
        const verdict = ensembleVerdictText(pooled)
        const market = pooled?.components.find((c) => c.name === 'market')
        const ensemble = pooled?.components.find((c) => c.name === 'ensemble')
        const diff = ensemble?.vsMarket
        return {
          value: verdict,
          valueClass: diff ? signalClass(diff.signal) : 'is-dim',
          say: market && ensemble && diff
            ? <>ATP+WTA log loss: market <span className="num">{market.logLoss.toFixed(4)}</span>, ensemble <span className="num">{ensemble.logLoss.toFixed(4)}</span>, {seMultiple(diff.mean, diff.standardError)} apart on {pooled?.n.toLocaleString()} matches.</>
            : 'No ATP or WTA match has every component and a market price yet.',
        }
      }} />
      <VerdictCard label="Closing-line value" query={predictions} render={(data) => {
        const all = data.clv.find((c) => c.group === 'all' && c.minGap === 0)
        if (!all || all.moved === 0) return { value: '—', valueClass: 'is-dim', say: 'No price has moved between prediction and close yet.' }
        return {
          value: pct(all.toward / all.moved),
          say: <>of {all.moved.toLocaleString()} moved prices moved toward the ensemble; the mean move over all {all.eligible.toLocaleString()} priced matches is <span className="num">{`${all.meanMoveToward >= 0 ? '+' : ''}${(all.meanMoveToward * 100).toFixed(2)}`}</span> pts.</>,
        }
      }} />
      <VerdictCard label="Standard total-games overs" query={lines} render={(data) => {
        const row = data.rows.find((r) => r.stat === 'total_games' && r.oddsType === 'standard')
        if (!row || row.overRate == null) return { value: '—', valueClass: 'is-dim', say: 'No settled standard total-games line yet.' }
        return {
          value: pct(row.overRate),
          valueClass: signalClass(row.signal),
          say: <>{row.standardError != null && <>&plusmn;<span className="num">{pct(row.standardError)}</span> on {row.settled.toLocaleString()} lines. </>}Break-even for a 2-3 pick Power entry is <span className="num">{row.breakEven != null ? pct(row.breakEven) : '—'}</span>.</>,
        }
      }} />
      <VerdictCard label="Confidence tiers" query={tiers} render={(data) => {
        const decided = data.tiers.filter((t) => t.verdict !== 'accruing')
        const furthest = [...data.tiers].sort((a, b) => b.verdictSampleSize - a.verdictSampleSize)[0]
        if (decided.length === 0) {
          return {
            value: 'Accruing',
            valueClass: 'is-dim',
            say: <>No tier has reached its <span className="num">{data.verdictSample}</span>-pick sample{furthest ? <>; {furthest.tier} is at <span className="num">{furthest.verdictSampleSize}</span></> : null}.</>,
          }
        }
        return {
          value: `${decided.length} of ${data.tiers.length} decided`,
          valueClass: 'is-dim',
          say: decided.map((t) => `${t.tier} ${t.verdict}`).join(', '),
        }
      }} />
    </section>
  )
}
