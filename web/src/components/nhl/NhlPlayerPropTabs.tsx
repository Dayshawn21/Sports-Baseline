import { useSearchParams } from 'react-router-dom'
import { NhlPlayerMarketSection } from '~/components/nhl/NhlPlayerMarketSection'
import { PlayerMarketTabs } from '~/components/shared/PlayerMarketTabs'
import type { NhlLineOnlyMarket, NhlPlayerProps } from '~/types/nhl'
import { playerSearch, propSectionIds } from '~/utils/nflPlayer'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlPlayerTabs, nhlSelectedMarket } from '~/utils/nhlPlayer'

/** The tab strip picks which market's card shows; `?market=` keeps the pick across a reload. */
export function NhlPlayerPropTabs({ player }: { player: NhlPlayerProps }) {
  const [params] = useSearchParams()
  const tabs = nhlPlayerTabs(player.markets) as NhlLineOnlyMarket[]
  const ids = propSectionIds(tabs)
  const selected = nhlSelectedMarket(params, tabs)
  const index = selected === null ? -1 : tabs.indexOf(selected as NhlLineOnlyMarket)
  const market = index === -1 ? undefined : player.markets.find(item => item.market === selected)
  return <PlayerMarketTabs heading={`Props on ${player.date}`} tabs={tabs.map(tab => ({ key: tab, label: nhlMarketLabel(tab) }))}
    selectedIndex={index} hrefFor={key => playerSearch(params, { market: key })}>
    {market && <NhlPlayerMarketSection key={ids[index]} id={ids[index]} player={player} market={market} />}
  </PlayerMarketTabs>
}
