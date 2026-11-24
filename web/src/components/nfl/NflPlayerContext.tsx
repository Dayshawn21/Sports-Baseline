import { NflUsageContext } from '~/components/nfl/NflEvidenceContext'
import type { NflPlayerWeek } from '~/utils/nflPlayer'

/** Usage is shown once, since it does not vary by prop; the game market lives on the game page. */
export function NflPlayerContext({ week }: { week: NflPlayerWeek | null }) {
  const first = week?.lines[0]
  if (!week || !first) return null
  return <section className="nfl-player-card nfl-player-prop" aria-label="Usage context">
    <div className="nfl-player-prop__body">
      <NflUsageContext row={first.row} game={week.game} />
    </div>
  </section>
}
