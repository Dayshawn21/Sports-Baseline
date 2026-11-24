import './player-panel.css'

export interface SegmentOption<T extends string> {
  value: T
  label: string
  /** Shown as the button's title; the option is disabled while it is set. */
  disabledReason?: string | null
}

interface SegmentSwitchProps<T extends string> {
  label: string
  options: Array<SegmentOption<T>>
  value: T
  onChange: (value: T) => void
}

/** The one squared switch the player pages use for a form window, a match or a surface. */
export function SegmentSwitch<T extends string>({ label, options, value, onChange }: SegmentSwitchProps<T>) {
  return <div className="nfl-prop-detail__switch" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" aria-pressed={option.value === value}
      disabled={Boolean(option.disabledReason)} title={option.disabledReason ?? undefined}
      onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>
}
