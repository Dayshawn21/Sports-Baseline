import { withAlpha } from '~/utils/color'

interface Props {
  value: number | string
  label: string
  color?: string
}

/** Compact count tile used in the page header rows. */
export default function StatChip({ value, label, color }: Props) {
  return (
    <div className="stat-chip" style={color ? { borderColor: withAlpha(color, 0.208) } : undefined}>
      <span className="stat-chip__value" style={{ color: color ?? 'var(--text-primary)' }}>{value}</span>
      <span className="stat-chip__label">{label}</span>
    </div>
  )
}
