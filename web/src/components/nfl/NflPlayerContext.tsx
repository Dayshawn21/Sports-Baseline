import { NflUsageContext } from '~/components/nfl/NflEvidenceContext'
import { DetailGameMarket } from '~/components/nfl/NflPropDetailSections'
import type { NflPlayerWeek } from '~/utils/nflPlayer'
import { nflPropDetail } from '~/utils/nflPropDetail'

/** The game market and usage are shown once, since they do not vary by prop. */
export function NflPlayerContext({ week, showUsage }: { week: NflPlayerWeek | null, showUsage: boolean }) {
  const first = week?.lines[0]
  if (!week || !first) return null
  const detail = nflPropDetail(first.row, week.game, first.alternates, Date.now())
  return <section className="nfl-player-card nfl-player-prop" aria-label="Game and usage context">
    <div className="nfl-player-prop__body">
      {showUsage && <NflUsageContext row={first.row} game={week.game} />}
      <DetailGameMarket detail={detail} />
    </div>
  </section>
}
