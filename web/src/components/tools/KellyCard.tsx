import { useState } from 'react'
import { Segmented } from 'antd'
import CalculatorCard, { CalcField, CalcResults, EMPTY_OUTPUT } from '~/components/tools/CalculatorCard'
import { kellyStake } from '~/utils/calculators'
import { DEFAULT_KELLY_MULTIPLIER } from '~/utils/oddsMath'
import { fmtPct } from '~/utils/odds'

const MULTIPLIERS = [
  { value: 1, label: 'Full' },
  { value: 0.5, label: 'Half' },
  { value: 0.25, label: 'Quarter' },
]

const LABELS = ['Fraction of bankroll', 'Stake'] as const

export default function KellyCard() {
  const [probability, setProbability] = useState('')
  const [odds, setOdds] = useState('')
  const [multiplier, setMultiplier] = useState(DEFAULT_KELLY_MULTIPLIER)
  const [bankroll, setBankroll] = useState('')

  return <CalculatorCard title="Kelly stake" hint="How much of a bankroll to bet, scaled down because a fair probability is an estimate.">
    <div className="tools-field-row">
      <CalcField label="Fair win probability" value={probability} onChange={setProbability} placeholder="55" suffix="%" />
      <CalcField label="Odds (American)" value={odds} onChange={setOdds} placeholder="-110" />
    </div>
    <div className="tools-field">
      <span className="tools-field__label">Kelly fraction</span>
      <Segmented block value={multiplier} onChange={value => setMultiplier(Number(value))} options={MULTIPLIERS} />
    </div>
    <CalcField label="Bankroll (optional)" value={bankroll} onChange={setBankroll} placeholder="1000" />
    <CalcResults
      parsed={kellyStake(probability, odds, multiplier, bankroll)}
      labels={LABELS}
      values={result => result.fraction === 0
        ? ['No bet', EMPTY_OUTPUT]
        : [fmtPct(result.fraction, 2), result.stake === null ? EMPTY_OUTPUT : result.stake.toFixed(2)]}
      note={result => result.capped ? 'Capped at 25% of bankroll.' : null}
    />
  </CalculatorCard>
}
