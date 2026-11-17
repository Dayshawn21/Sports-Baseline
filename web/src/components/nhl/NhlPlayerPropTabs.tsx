import { useSearchParams } from 'react-router-dom'
import { NhlPlayerMarketSection } from '~/components/nhl/NhlPlayerMarketSection'
import { PlayerMarketTabs } from '~/components/shared/PlayerMarketTabs'
import type { NhlPlayerProps } from '~/types/nhl'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { playerSearch, playerTabs, propSectionIds, selectedMarket } from '~/utils/playerPage'

/** The tab strip picks which market's card shows; `?market=` keeps the pick across a reload. */
export function NhlPlayerPropTabs({ player }: { player: NhlPlayerProps }) {
  const [params] = useSearchParams()
  const tabs = playerTabs(player.markets)
  const ids = propSectionIds(tabs)
  const selected = selectedMarket(params, tabs)
  const index = selected === null ? -1 : tabs.indexOf(selected)
  const market = index === -1 ? undefined : player.markets.find(item => item.market === selected)
  return <PlayerMarketTabs heading={`Props on ${player.date}`} tabs={tabs.map(tab => ({ key: tab, label: nhlMarketLabel(tab) }))}
    selectedIndex={index} hrefFor={key => playerSearch(params, { market: key })}>
    {market && <NhlPlayerMarketSection key={ids[index]} id={ids[index]} player={player} market={market} />}
  </PlayerMarketTabs>
}
