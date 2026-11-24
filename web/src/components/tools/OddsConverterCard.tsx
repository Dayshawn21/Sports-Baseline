import { useState } from 'react'
import { Segmented } from 'antd'
import CalculatorCard, { CalcField, CalcResults } from '~/components/tools/CalculatorCard'
import { convertOdds, fmtDecimalOdds, type OddsFormat } from '~/utils/calculators'
import { fmtAmerican, fmtPct } from '~/utils/odds'

const FORMATS: { value: OddsFormat, label: string, placeholder: string, suffix?: string }[] = [
  { value: 'american', label: 'American', placeholder: '-110' },
  { value: 'decimal', label: 'Decimal', placeholder: '1.91' },
  { value: 'probability', label: 'Probability', placeholder: '52.4', suffix: '%' },
]

const LABELS = ['American', 'Decimal', 'Implied probability'] as const

export default function OddsConverterCard() {
  const [format, setFormat] = useState<OddsFormat>('american')
  const [text, setText] = useState('')
  const active = FORMATS.find(entry => entry.value === format) ?? FORMATS[0]

  return <CalculatorCard title="Odds converter" hint="One price in any format, shown in the other two.">
    <Segmented
      block
      value={format}
      onChange={value => { setFormat(value as OddsFormat); setText('') }}
      options={FORMATS.map(({ value, label }) => ({ value, label }))}
    />
    <CalcField label={`${active.label} odds`} value={text} onChange={setText} placeholder={active.placeholder} suffix={active.suffix} />
    <CalcResults
      parsed={convertOdds(format, text)}
      labels={LABELS}
      values={odds => [fmtAmerican(odds.american), fmtDecimalOdds(odds.decimal), fmtPct(odds.probability)]}
    />
  </CalculatorCard>
}
