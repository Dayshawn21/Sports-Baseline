import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflUsageContext } from '~/components/nfl/NflEvidenceContext'
import { DetailGameMarket } from '~/components/nfl/NflPropDetailSections'
import { NflPlayerPropSection } from '~/components/nfl/NflPlayerPropSection'
import { marketLabel } from '~/utils/nflLabels'
import { useNflGameContext } from '~/hooks/useNfl'
import { evidenceContextGameId } from '~/utils/nflEvidenceContext'
import { propSectionIds, selectedPropMarket, type NflPlayerWeek } from '~/utils/nflPlayer'
import { nflPropDetail } from '~/utils/nflPropDetail'

const TABS_ID = 'prop-tabs'

export function scrollToPropTabs() {
  document.getElementById(TABS_ID)?.scrollIntoView({ block: 'start' })
}

/** The game market and usage are shown once, since they do not vary by prop; the tabs under them pick which prop's evidence shows. */
export function NflPlayerProps({ week, showUsage }: { week: NflPlayerWeek, showUsage: boolean }) {
  const markets = week.lines.map(item => item.row.market)
  const ids = propSectionIds(markets)
  const first = week.lines[0]
  const detail = nflPropDetail(first.row, week.game, first.alternates, Date.now())
  const [params] = useSearchParams()
  const market = selectedPropMarket(params, markets)
  const selectedIndex = market === null ? 0 : markets.indexOf(market)
  const shown = week.lines[selectedIndex]
  // The usage card above the tabs grows when its query settles, so a deep link scrolls once that has happened.
  const usageSettling = useNflGameContext(showUsage ? evidenceContextGameId(week.game, first.row) : null).isFetching
  const scrolled = useRef(false)
  useEffect(() => {
    if (market === null || usageSettling || scrolled.current) return
    scrolled.current = true
    scrollToPropTabs()
  }, [market, usageSettling])
  return <>
    <h2 className="nfl-player-section-title">This week's props <small>{week.lines.length} {week.lines.length === 1 ? 'line' : 'lines'}</small></h2>
    <section className="nfl-player-card nfl-player-prop" aria-label="Game and usage context">
      <div className="nfl-player-prop__body">
        {showUsage && <NflUsageContext row={first.row} game={week.game} />}
        <DetailGameMarket detail={detail} />
      </div>
    </section>
    <nav id={TABS_ID} className="nfl-player-jump" aria-label="Choose a prop">
      {week.lines.map((item, index) => <Link key={ids[index]} to={`?market=${encodeURIComponent(item.row.market)}`} replace
        aria-current={index === selectedIndex ? 'true' : undefined}>{marketLabel(item.row.market)}</Link>)}
    </nav>
    <NflPlayerPropSection key={ids[selectedIndex]} id={ids[selectedIndex]} item={shown} game={week.game} />
  </>
}
