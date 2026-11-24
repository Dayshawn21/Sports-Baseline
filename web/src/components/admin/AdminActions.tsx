import { Button } from 'antd'
import { hasEloFlag, hasStatsFlag } from '~/utils/adminFlags'

export type AdminPanel = 'stats' | 'fetch-elo' | 'set-elo'

interface Props {
  flags: string[]
  open: AdminPanel | null | undefined
  onToggle: (panel: AdminPanel) => void
  compact: boolean
}

/** The repair buttons a player's flags call for; the open panel's button is highlighted. */
export function AdminActions({ flags, open, onToggle, compact }: Props) {
  const buttons: { panel: AdminPanel, label: string, shown: boolean }[] = [
    { panel: 'stats', label: 'Fix Stats', shown: hasStatsFlag(flags) },
    { panel: 'fetch-elo', label: 'Fetch ELO', shown: hasEloFlag(flags) },
    { panel: 'set-elo', label: 'Set ELO', shown: hasEloFlag(flags) },
  ]
  return <div style={compact ? { marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' } : { display: 'flex', gap: 8, flexWrap: 'wrap' }}>
    {buttons.filter(button => button.shown).map(({ panel, label }) => (
      <Button key={panel} size="small" type={open === panel ? 'primary' : 'default'} onClick={() => onToggle(panel)}
        style={compact ? undefined : { fontSize: 12 }}>{label}</Button>
    ))}
  </div>
}
