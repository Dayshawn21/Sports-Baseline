import { Link, useSearchParams } from 'react-router-dom'
import { NbaPlayerMarketSection } from '~/components/nba/NbaPlayerMarketSection'
import type { NbaPlayerProps } from '~/types/nba'
import { nbaMarketLabel } from '~/utils/nbaLineOnly'
import { nbaPlayerTabs, nbaSelectedMarket } from '~/utils/nbaPlayer'
import { playerSearch, propSectionIds } from '~/utils/nflPlayer'

const TABS_ID = 'prop-tabs'

/** The tab strip picks which market's card shows; `?market=` keeps the pick across a reload. */
export function NbaPlayerPropTabs({ player }: { player: NbaPlayerProps }) {
  const [params] = useSearchParams()
  const tabs = nbaPlayerTabs(player.markets)
  const ids = propSectionIds(tabs)
  const selected = nbaSelectedMarket(params, tabs)
  const index = selected === null ? -1 : tabs.indexOf(selected)
  const market = index === -1 ? undefined : player.markets.find(item => item.market === selected)
  if (tabs.length === 0) return null
  return <>
    <h2 className="nfl-player-section-title">Props on {player.date} <small>{tabs.length} {tabs.length === 1 ? 'market' : 'markets'}</small></h2>
    <nav id={TABS_ID} className="nfl-player-jump" aria-label="Choose a prop">
      {tabs.map((tab, position) => <Link key={ids[position]} to={playerSearch(params, { market: tab })} replace
        aria-current={position === index ? 'true' : undefined}>{nbaMarketLabel(tab)}</Link>)}
    </nav>
    {market && <NbaPlayerMarketSection key={ids[index]} id={ids[index]} player={player} market={market} />}
  </>
}
