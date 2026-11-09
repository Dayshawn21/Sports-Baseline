import StatChip from '~/components/shared/StatChip'
import type { PlayerHeadChip } from '~/utils/playerProjection'

/** The page head's stat chips, the NFL player page's pattern; nothing when there are none. */
export function PlayerHeadChips({ chips }: { chips: PlayerHeadChip[] }) {
  if (chips.length === 0) return null
  return <section className="page-head__stats nfl-player-stats" aria-label="At a glance">
    {chips.map(chip => <StatChip key={chip.label} value={chip.value} label={chip.label} />)}
  </section>
}
