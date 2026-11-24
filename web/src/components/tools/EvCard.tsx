import { useState } from 'react'
import CalculatorCard, { CalcField, CalcResults, EMPTY_OUTPUT } from '~/components/tools/CalculatorCard'
import { betEv, fmtSignedAmount, fmtSignedPct } from '~/utils/calculators'
import { fmtPct } from '~/utils/odds'

const LABELS = ['EV per unit', 'EV on stake', 'Break-even probability'] as const

export default function EvCard() {
  const [probability, setProbability] = useState('')
  const [odds, setOdds] = useState('')
  const [stake, setStake] = useState('')

  return <CalculatorCard title="Expected value" hint="What a bet returns on average, given your fair win probability.">
    <div className="tools-field-row">
      <CalcField label="Fair win probability" value={probability} onChange={setProbability} placeholder="55" suffix="%" />
      <CalcField label="Odds (American)" value={odds} onChange={setOdds} placeholder="-110" />
    </div>
    <CalcField label="Stake (optional)" value={stake} onChange={setStake} placeholder="100" />
    <CalcResults
      parsed={betEv(probability, odds, stake)}
      labels={LABELS}
      values={result => [
        fmtSignedPct(result.ev),
        result.evAmount === null ? EMPTY_OUTPUT : fmtSignedAmount(result.evAmount),
        fmtPct(result.breakEven),
      ]}
    />
  </CalculatorCard>
}
