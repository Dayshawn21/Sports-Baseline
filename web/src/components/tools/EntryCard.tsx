import { useState } from 'react'
import { Button, Segmented } from 'antd'
import CalculatorCard, { CalcField, CalcResults } from '~/components/tools/CalculatorCard'
import { entryView, fmtSignedPct } from '~/utils/calculators'
import { fmtPct } from '~/utils/odds'
import { MAX_LEGS, MIN_LEGS, type EntryKind } from '~/utils/prizepicksEntry'

const LABELS = ['Expected payout', 'EV per unit'] as const
const MIN_FLEX_LEGS = 3

function fmtMultiple(multiple: number): string {
  return `${Number(multiple.toFixed(3))}x`
}

export default function EntryCard() {
  const [kind, setKind] = useState<EntryKind>('power')
  const [legs, setLegs] = useState(['', '', ''])
  const minLegs = kind === 'flex' ? MIN_FLEX_LEGS : MIN_LEGS
  const parsed = entryView(kind, legs)

  const setLeg = (index: number, text: string) => setLegs(current => current.map((leg, at) => at === index ? text : leg))

  return <CalculatorCard title="PrizePicks entry EV" hint="Power and flex payouts from each leg's own hit probability.">
    <Segmented
      block
      value={kind}
      onChange={value => setKind(value as EntryKind)}
      options={[
        { value: 'power', label: 'Power' },
        { value: 'flex', label: 'Flex', disabled: legs.length < MIN_FLEX_LEGS },
      ]}
    />
    <div className="tools-legs">
      {legs.map((leg, index) => <div key={index} className="tools-leg">
        <CalcField label={`Leg ${index + 1}`} value={leg} onChange={text => setLeg(index, text)} placeholder="58" suffix="%" />
        <Button
          type="text"
          aria-label={`Remove leg ${index + 1}`}
          disabled={legs.length <= minLegs}
          onClick={() => setLegs(current => current.filter((_, at) => at !== index))}
        >
          Remove
        </Button>
      </div>)}
    </div>
    <Button disabled={legs.length >= MAX_LEGS} onClick={() => setLegs(current => [...current, ''])}>Add leg</Button>
    <CalcResults
      parsed={parsed}
      labels={LABELS}
      values={view => [fmtMultiple(view.expectedMultiple), fmtSignedPct(view.ev)]}
    >
      {parsed.state === 'ok' && <table className="tools-entry-table">
        <thead><tr><th scope="col">Hits</th><th scope="col">Chance</th><th scope="col">Pays</th></tr></thead>
        <tbody>
          {parsed.value.rows.map(row => <tr key={row.hits}>
            <td>{row.hits} of {legs.length}</td>
            <td>{fmtPct(row.probability)}</td>
            <td>{row.multiple === null ? 'Nothing' : fmtMultiple(row.multiple)}</td>
          </tr>)}
        </tbody>
      </table>}
      <p className="tools-results__reason">Standard payouts as of 2026-11-11, without goblins, demons or promos. Check the app before entering.</p>
    </CalcResults>
  </CalculatorCard>
}
