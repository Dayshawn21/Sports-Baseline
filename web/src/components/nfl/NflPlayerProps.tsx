import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { NflUsageContext } from '~/components/nfl/NflEvidenceContext'
import { DetailGameMarket } from '~/components/nfl/NflPropDetailSections'
import { NflPlayerOtherMarketSection } from '~/components/nfl/NflPlayerOtherMarketSection'
import { NflPlayerPropSection } from '~/components/nfl/NflPlayerPropSection'
import type { NflOtherMarkets } from '~/types/nfl'
import { marketLabel } from '~/utils/nflLabels'
import { useNflGameContext } from '~/hooks/useNfl'
import { evidenceContextGameId } from '~/utils/nflEvidenceContext'
import { playerSearch, propSectionIds, selectedPropMarket, type NflPlayerWeek } from '~/utils/nflPlayer'
import { playerTabs } from '~/utils/nflOtherMarkets'
import { nflPropDetail } from '~/utils/nflPropDetail'

const TABS_ID = 'prop-tabs'

export function scrollToPropTabs() {
  document.getElementById(TABS_ID)?.scrollIntoView({ block: 'start' })
}

export interface OtherMarketsState {
  data: NflOtherMarkets | undefined
  isLoading: boolean
  isError: boolean
}

/** The game market and usage are shown once, since they do not vary by prop; the tabs under them pick which prop's evidence shows. Line-only markets are tabs too, with recent results only. */
export function NflPlayerProps({ week, others, showUsage }: { week: NflPlayerWeek | null, others: OtherMarketsState, showUsage: boolean }) {
  const modelMarkets = week?.lines.map(item => item.row.market) ?? []
  const otherMarkets = others.data?.markets ?? []
  const tabs = playerTabs(modelMarkets, otherMarkets.map(item => item.market))
  const ids = propSectionIds(tabs.map(tab => tab.market))
  const first = week?.lines[0]
  const detail = week && first ? nflPropDetail(first.row, week.game, first.alternates, Date.now()) : null
  const [params] = useSearchParams()
  const market = selectedPropMarket(params, tabs.map(tab => tab.market))
  const selectedIndex = market === null ? 0 : tabs.findIndex(tab => tab.market === market)
  const selected = tabs[selectedIndex]
  // The usage card above the tabs grows when its query settles, so a deep link scrolls once that has happened.
  const usageSettling = useNflGameContext(showUsage && week && first ? evidenceContextGameId(week.game, first.row) : null).isFetching
  const scrolled = useRef(false)
  useEffect(() => {
    if (market === null || usageSettling || scrolled.current) return
    scrolled.current = true
    scrollToPropTabs()
  }, [market, usageSettling])
  const selectedOther = selected?.kind === 'other' ? otherMarkets.find(item => item.market === selected.market) : undefined
  const selectedModel = selected?.kind === 'model' ? week?.lines.find(item => item.row.market === selected.market) : undefined
  return <>
    {week && first && detail && <>
      <h2 className="nfl-player-section-title">This week's props <small>{week.lines.length} {week.lines.length === 1 ? 'line' : 'lines'}</small></h2>
      <section className="nfl-player-card nfl-player-prop" aria-label="Game and usage context">
        <div className="nfl-player-prop__body">
          {showUsage && <NflUsageContext row={first.row} game={week.game} />}
          <DetailGameMarket detail={detail} />
        </div>
      </section>
    </>}
    {!week && tabs.length > 0 && <h2 className="nfl-player-section-title">This week's markets <small>Recent results only, no model comparison</small></h2>}
    {tabs.length > 0 && <nav id={TABS_ID} className="nfl-player-jump" aria-label="Choose a prop">
      {tabs.map((tab, index) => <Link key={ids[index]} to={playerSearch(params, { market: tab.market })} replace
        aria-current={index === selectedIndex ? 'true' : undefined}>{marketLabel(tab.market)}</Link>)}
    </nav>}
    {others.isLoading && <p className="nfl-player-note">Loading other markets...</p>}
    {others.isError && <p className="nfl-player-note">Other markets could not be loaded.</p>}
    {selectedModel && week && <NflPlayerPropSection key={ids[selectedIndex]} id={ids[selectedIndex]} item={selectedModel} game={week.game} />}
    {selectedOther && <NflPlayerOtherMarketSection key={ids[selectedIndex]} id={ids[selectedIndex]} market={selectedOther} opponent={others.data?.opponent ?? null} />}
  </>
}
