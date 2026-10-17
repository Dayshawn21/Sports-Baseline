import type { CSSProperties } from 'react'
import type { NflClvMarket, NflClvRow, NflModelClv } from '~/types/nfl'
import { signedPoints, verdictLabel } from '~/utils/nflTrackRecord'
import { sampleProgress, signalClass } from '~/utils/trackRecord'

const MARKET_TITLES: Record<NflClvMarket['market'], string> = { spread: 'Spread', total: 'Total' }

function Row({ label, value }: { label: string, value: string }) {
  return <div className="nfl-model-rate is-plain"><span>{label}</span><b>{value}</b></div>
}

function splitValue(row: NflClvRow): string {
  return row.n === 0 ? 'no picks' : `${signedPoints(row.meanClv)} on ${row.n}`
}

function MarketCard({ market, verdictPicks }: { market: NflClvMarket, verdictPicks: number }) {
  const { headline } = market
  const tone = signalClass(market.signal)
  const progress = { '--w': `${sampleProgress(headline.n, verdictPicks) * 100}%` } as CSSProperties
  const decided = market.verdict !== 'accruing'
  return (
    <section className="nfl-model-card">
      <div className="nfl-model-card__head">
        <span className="nfl-model-label">{MARKET_TITLES[market.market]} · {market.modelVersion}</span>
        <span className={`nfl-model-tag ${tone}`}>{verdictLabel(market.verdict)}</span>
      </div>
      <div className="nfl-model-card__body">
        {headline.n === 0
          ? <div className="nfl-model-headline"><span className="nfl-model-big nfl-model-dim">No picks yet</span></div>
          : <div className="nfl-model-headline">
            <span className={`nfl-model-big ${tone}`}>{signedPoints(headline.meanClv)}</span>
            <span className="nfl-model-dim">
              {headline.standardError !== null && <>&plusmn; {headline.standardError.toFixed(2)} </>}
              pts · {headline.n} picks{decided && ' in the verdict sample'}
            </span>
          </div>}
        <div className="nfl-model-progress nfl-model-clv__progress" style={progress}><i /></div>
        <div className="nfl-model-muted">{Math.min(headline.n, verdictPicks)} of {verdictPicks} picks to a verdict</div>
        <div className="nfl-model-rates">
          <Row label="Toward / away / flat" value={`${headline.toward} / ${headline.away} / ${headline.flat}`} />
          <Row label="Vs entry line" value={`${headline.wins}-${headline.losses}-${headline.pushes}`} />
          <Row
            label="Entry lead time"
            value={market.medianLeadHours === null ? '—' : `${Math.round(market.medianLeadHours)} h median`}
          />
          <Row label="Weeks 1-4" value={splitValue(market.early)} />
          <Row label="Weeks 5+" value={splitValue(market.late)} />
        </div>
        <p className="nfl-model-note">
          {market.graded} games graded
          {Object.entries(market.excluded).map(([reason, n]) => `, ${n} ${reason}`).join('')}.
        </p>
      </div>
    </section>
  )
}

export default function NflGameLineClv({ data }: { data: NflModelClv }) {
  const { rule } = data
  return <>
    <div className="nfl-model-grid">
      {data.markets.map((market) => <MarketCard key={market.market} market={market} verdictPicks={rule.verdictPicks} />)}
    </div>
    <p className="nfl-model-rule">
      <b>Pre-registered rule (fixed 2026-09-26).</b> A pick is |model - entry| &ge; {rule.pickThreshold} points, where
      the entry line is the earliest stored line after the previous week&apos;s games. CLV is how far the close moved
      toward the model, in points. The verdict sample is the first whole weeks holding {rule.verdictPicks} picks per
      market. Pass only if mean CLV minus 2 SE is above zero; a reject is final for these model versions. W-L-P, lead
      time and the week split are context only. Only a pass would justify a bettable tag on the slate.
    </p>
  </>
}
