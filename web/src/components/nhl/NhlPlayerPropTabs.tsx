import { Link, useSearchParams } from 'react-router-dom'
import { NhlPlayerMarketSection } from '~/components/nhl/NhlPlayerMarketSection'
import type { NhlLineOnlyMarket, NhlPlayerProps } from '~/types/nhl'
import { playerSearch, propSectionIds } from '~/utils/nflPlayer'
import { nhlMarketLabel } from '~/utils/nhlLineOnly'
import { nhlPlayerTabs, nhlSelectedMarket } from '~/utils/nhlPlayer'

const TABS_ID = 'prop-tabs'

/** The tab strip picks which market's card shows; `?market=` keeps the pick across a reload. */
export function NhlPlayerPropTabs({ player }: { player: NhlPlayerProps }) {
  const [params] = useSearchParams()
  const tabs = nhlPlayerTabs(player.markets) as NhlLineOnlyMarket[]
  const ids = propSectionIds(tabs)
  const selected = nhlSelectedMarket(params, tabs)
  const index = selected === null ? -1 : tabs.indexOf(selected as NhlLineOnlyMarket)
  const market = index === -1 ? undefined : player.markets.find(item => item.market === selected)
  if (tabs.length === 0) return null
  return <>
    <h2 className="nfl-player-section-title">Props on {player.date} <small>{tabs.length} {tabs.length === 1 ? 'market' : 'markets'}</small></h2>
    <nav id={TABS_ID} className="nfl-player-jump" aria-label="Choose a prop">
      {tabs.map((tab, position) => <Link key={ids[position]} to={playerSearch(params, { market: tab })} replace
        aria-current={position === index ? 'true' : undefined}>{nhlMarketLabel(tab)}</Link>)}
    </nav>
    {market && <NhlPlayerMarketSection key={ids[index]} id={ids[index]} player={player} market={market} />}
  </>
}
