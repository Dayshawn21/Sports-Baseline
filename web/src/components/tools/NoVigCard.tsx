import { useState } from 'react'
import CalculatorCard, { CalcField, CalcResults } from '~/components/tools/CalculatorCard'
import { noVig } from '~/utils/calculators'
import { fmtAmerican, fmtPct } from '~/utils/odds'

const LABELS = ['Side A fair', 'Side B fair', 'Side A fair odds', 'Side B fair odds', 'Overround'] as const

export default function NoVigCard() {
  const [sideA, setSideA] = useState('')
  const [sideB, setSideB] = useState('')

  return <CalculatorCard title="No-vig fair odds" hint="Both sides of a two-way market, with the book's margin removed.">
    <div className="tools-field-row">
      <CalcField label="Side A odds" value={sideA} onChange={setSideA} placeholder="-150" />
      <CalcField label="Side B odds" value={sideB} onChange={setSideB} placeholder="+130" />
    </div>
    <CalcResults
      parsed={noVig(sideA, sideB)}
      labels={LABELS}
      values={result => [
        fmtPct(result.fairA),
        fmtPct(result.fairB),
        fmtAmerican(result.americanA),
        fmtAmerican(result.americanB),
        fmtPct(result.overround),
      ]}
    />
  </CalculatorCard>
}
