import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflUsageContext } from '~/components/nfl/NflEvidenceContext'
import { DetailGameMarket } from '~/components/nfl/NflPropDetailSections'
import { NflPlayerPropSection } from '~/components/nfl/NflPlayerPropSection'
import { marketLabel } from '~/utils/nflLabels'
import { useNflGameContext } from '~/hooks/useNfl'
import { evidenceContextGameId } from '~/utils/nflEvidenceContext'
import { propSectionIds, selectedPropMarket, type NflPlayerWeek } from '~/utils/nflPlayer'
import { nflPropDetail } from '~/utils/nflPropDetail'

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ block: 'start' })
}

/** Every full-game prop the player has this week, expanded; the game market and usage are shown once, since they do not vary by prop. */
export function NflPlayerProps({ week, showUsage }: { week: NflPlayerWeek, showUsage: boolean }) {
  const ids = propSectionIds(week.lines.map(item => item.row.market))
  const first = week.lines[0]
  const detail = nflPropDetail(first.row, week.game, first.alternates, Date.now())
  const [params] = useSearchParams()
  const market = selectedPropMarket(params, week.lines.map(item => item.row.market))
  const selectedId = market === null ? null : ids[week.lines.findIndex(item => item.row.market === market)]
  // The usage card above the sections grows when its query settles, so scroll once that has happened.
  const usageSettling = useNflGameContext(showUsage ? evidenceContextGameId(week.game, first.row) : null).isFetching
  useEffect(() => {
    if (selectedId !== null && !usageSettling) scrollToSection(selectedId)
  }, [selectedId, usageSettling])
  return <>
    <h2 className="nfl-player-section-title">This week's props <small>{week.lines.length} {week.lines.length === 1 ? 'line' : 'lines'}</small></h2>
    <nav className="nfl-player-jump" aria-label="Jump to a prop">
      {week.lines.map((item, index) => <Link key={ids[index]} to={`?market=${encodeURIComponent(item.row.market)}`} replace
        aria-current={ids[index] === selectedId ? 'true' : undefined} onClick={() => scrollToSection(ids[index])}>{marketLabel(item.row.market)}</Link>)}
    </nav>
    <section className="nfl-player-card nfl-player-prop" aria-label="Game and usage context">
      <div className="nfl-player-prop__body">
        {showUsage && <NflUsageContext row={first.row} game={week.game} />}
        <DetailGameMarket detail={detail} gameLink={null} />
      </div>
    </section>
    {week.lines.map((item, index) => <NflPlayerPropSection key={ids[index]} id={ids[index]} item={item} game={week.game} selected={ids[index] === selectedId} />)}
  </>
}
