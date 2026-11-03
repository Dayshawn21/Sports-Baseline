import { useSearchParams } from 'react-router-dom'
import { NflPlayerOtherMarketSection } from '~/components/nfl/NflPlayerOtherMarketSection'
import { NflPlayerPropSection } from '~/components/nfl/NflPlayerPropSection'
import { PlayerMarketTabs, TABS_ID } from '~/components/shared/PlayerMarketTabs'
import type { NflOtherMarkets } from '~/types/nfl'
import { marketLabel } from '~/utils/nflLabels'
import { playerSearch, propSectionIds, selectedPropMarket, type NflPlayerWeek } from '~/utils/nflPlayer'
import { playerTabs } from '~/utils/nflOtherMarkets'

export function scrollToPropTabs() {
  document.getElementById(TABS_ID)?.scrollIntoView({ block: 'start' })
}

export interface OtherMarketsState {
  data: NflOtherMarkets | undefined
  isLoading: boolean
  isError: boolean
}

/** The tabs pick which prop's evidence shows. Line-only markets are tabs too, with recent results only. */
export function NflPlayerProps({ week, others, weekNumber }: { week: NflPlayerWeek | null, others: OtherMarketsState, weekNumber: number }) {
  const modelMarkets = week?.lines.map(item => item.row.market) ?? []
  const otherMarkets = others.data?.markets ?? []
  const tabs = playerTabs(modelMarkets, otherMarkets.map(item => item.market))
  const ids = propSectionIds(tabs.map(tab => tab.market))
  const [params] = useSearchParams()
  const market = selectedPropMarket(params, tabs.map(tab => tab.market))
  const selectedIndex = market === null ? 0 : tabs.findIndex(tab => tab.market === market)
  const selected = tabs[selectedIndex]
  const selectedOther = selected?.kind === 'other' ? otherMarkets.find(item => item.market === selected.market) : undefined
  const selectedModel = selected?.kind === 'model' ? week?.lines.find(item => item.row.market === selected.market) : undefined
  return <>
    <PlayerMarketTabs heading={`Props for week ${weekNumber}`} note={week ? undefined : 'Recent results only, no model comparison'}
      tabs={tabs.map(tab => ({ key: tab.market, label: marketLabel(tab.market) }))} selectedIndex={selectedIndex}
      hrefFor={key => playerSearch(params, { market: key })}>
      {selectedModel && week && <NflPlayerPropSection key={ids[selectedIndex]} id={ids[selectedIndex]} item={selectedModel} game={week.game} />}
      {selectedOther && <NflPlayerOtherMarketSection key={ids[selectedIndex]} id={ids[selectedIndex]} market={selectedOther} opponent={others.data?.opponent ?? null} />}
    </PlayerMarketTabs>
    {others.isLoading && <p className="nfl-player-note">Loading other markets...</p>}
    {others.isError && <p className="nfl-player-note">Other markets could not be loaded.</p>}
  </>
}
