import type { ReactNode } from 'react'
import { Input } from 'antd'
import type { Parsed } from '~/utils/calculatorInputs'
import { fmtPct } from '~/utils/odds'

/** The shared placeholder for an output with no valid input yet. */
export const EMPTY_OUTPUT = fmtPct(null)

interface CalculatorCardProps {
  title: string
  /** One line on what the card answers. */
  hint: string
  children: ReactNode
}

export default function CalculatorCard({ title, hint, children }: CalculatorCardProps) {
  return <section className="tools-card" aria-label={title}>
    <header className="tools-card__head">
      <h2 className="tools-card__title">{title}</h2>
      <p className="tools-card__hint">{hint}</p>
    </header>
    {children}
  </section>
}

interface CalcFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  suffix?: string
}

export function CalcField({ label, value, onChange, placeholder, suffix }: CalcFieldProps) {
  return <label className="tools-field">
    <span className="tools-field__label">{label}</span>
    <Input
      value={value}
      onChange={event => onChange(event.target.value)}
      placeholder={placeholder}
      // An always-present node: antd drops focus when a suffix appears or disappears (the converter's %).
      suffix={suffix ?? <span />}
      inputMode="decimal"
      autoComplete="off"
    />
  </label>
}

interface CalcResultsProps<T> {
  parsed: Parsed<T>
  labels: readonly string[]
  /** One value per label, in the same order. */
  values: (value: T) => string[]
  /** A line under the rows for a valid result, such as a cap that bound. */
  note?: (value: T) => string | null
  children?: ReactNode
}

/** Output rows, reading the placeholder until the input is valid, plus the reason when it is invalid. */
export function CalcResults<T>({ parsed, labels, values, note, children }: CalcResultsProps<T>) {
  const shown = parsed.state === 'ok' ? values(parsed.value) : labels.map(() => EMPTY_OUTPUT)
  const noteText = parsed.state === 'ok' && note ? note(parsed.value) : null
  return <div className="tools-results">
    <dl className="tools-results__rows">
      {labels.map((label, index) => <div key={label}>
        <dt>{label}</dt>
        <dd>{shown[index]}</dd>
      </div>)}
    </dl>
    {noteText && <p className="tools-results__reason">{noteText}</p>}
    {parsed.state === 'invalid' && <p className="tools-results__reason" role="status">{parsed.reason}</p>}
    {children}
  </div>
}
