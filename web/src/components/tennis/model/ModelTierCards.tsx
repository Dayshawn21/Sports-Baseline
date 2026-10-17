import type { CSSProperties } from 'react'
import type { ModelPropTiersResponse, TrackTierRow } from '~/types/tennis'
import { sampleProgress, signalClass } from '~/utils/trackRecord'

const pct = (value: number) => `${(value * 100).toFixed(1)}%`

const VERDICT_LABELS: Record<Exclude<TrackTierRow['verdict'], 'accruing'>, string> = {
  pass: 'Beats break-even',
  reject: 'Does not beat break-even',
}

function TierCard({ tier, sample }: { tier: TrackTierRow, sample: number }) {
  const progress = { '--w': `${sampleProgress(tier.verdictSampleSize, sample) * 100}%` } as CSSProperties
  // Until the verdict is in, the running rate is a small, correlated sample, so it stays gray.
  const valueClass = tier.verdict === 'accruing' ? 'is-dim' : signalClass(tier.signal)
  return (
    <div className="tennis-model-card tennis-model-tier">
      <div className="tennis-model-tier__name">{tier.tier}</div>
      {tier.decided === 0
        ? <div className="tennis-model-tier__value is-dim">No picks yet</div>
        : <>
          <div className={`tennis-model-tier__value ${valueClass}`}>{tier.hits} / {tier.decided}</div>
          <div className="tennis-model-tier__sub">
            {tier.hitRate != null && pct(tier.hitRate)}
            {tier.standardError != null && <> &plusmn;{pct(tier.standardError)}</>}
            {tier.pushes > 0 && <> · {tier.pushes} push{tier.pushes === 1 ? '' : 'es'}</>}
          </div>
        </>}
      <div className="tennis-model-progress" style={progress}><i /></div>
      <div className="tennis-model-tier__foot">
        {tier.verdict === 'accruing'
          ? <>{tier.verdictSampleSize} of {sample} picks to a verdict</>
          : <span className={signalClass(tier.signal)}>
            {VERDICT_LABELS[tier.verdict]}
            {tier.verdictHitRate != null && <> · {pct(tier.verdictHitRate)} on {tier.verdictSampleSize}</>}
          </span>}
      </div>
    </div>
  )
}

export default function ModelTierCards({ data }: { data: ModelPropTiersResponse }) {
  return (
    <>
      <section className="tennis-model-tiers" aria-label="Hit rate by confidence tier">
        {data.tiers.map((tier) => <TierCard key={tier.tier} tier={tier} sample={data.verdictSample} />)}
        <div className="tennis-model-card tennis-model-tier">
          <div className="tennis-model-tier__name">PASS</div>
          <div className="tennis-model-tier__value is-dim">{data.passSnapshotted.toLocaleString()}</div>
          <div className="tennis-model-tier__sub">snapshotted, not a pick, not graded</div>
          <div className="tennis-model-progress" style={{ '--w': '0%' } as CSSProperties}><i /></div>
          <div className="tennis-model-tier__foot">kept for reference</div>
        </div>
      </section>
      <p className="tennis-model-note">
        Graded from <code>prop_projection_snapshots</code> frozen before the start, {data.projectionVersion} standard
        lines only, against the {pct(data.breakEven)} per-leg break-even. The verdict sample is each tier&apos;s first
        whole snapshot days, 3 or more days old, holding {data.verdictSample} decided picks; it passes only if its hit
        rate minus 2 SE beats break-even, and a reject is final for {data.projectionVersion}. Rates stay gray until
        then. {data.excluded.nonStandard.toLocaleString()} goblin and demon picks are not graded here, and{' '}
        {data.excluded.awaiting.toLocaleString()} standard picks are still waiting to settle.
      </p>
    </>
  )
}
