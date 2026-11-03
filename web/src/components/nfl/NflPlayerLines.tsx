import { Link, useSearchParams } from 'react-router-dom'
import { scrollToPropTabs } from '~/components/nfl/NflPlayerProps'
import { formatKickoffTime, formatProjection, marketLabel } from '~/utils/nflLabels'
import { playerSearch, selectedPropMarket, type NflPlayerWeek, type NflPlayerWeekLine } from '~/utils/nflPlayer'
import { edgeLabel, edgePctLabel } from '~/utils/nflSignal'
import { isTargetsReference, TARGETS_REFERENCE_NOTE } from '~/utils/nflTargets'

const TD = 'anytime_touchdown'

function LineRow({ item, selected, params, onJump }: { item: NflPlayerWeekLine, selected: boolean, params: URLSearchParams, onJump: () => void }) {
  const { row } = item
  const isTd = row.market === TD
  const reference = isTargetsReference(row.market)
  // The de-vigged price where there is one, else the raw price, as the prop cards read it.
  const bookPrice = row.bookProbabilityDevigged ?? row.bookProbability
  const books = bookPrice === null ? 'no books' : `books ${formatProjection(TD, bookPrice)}`
  return <Link to={playerSearch(params, { market: row.market })} replace className={`nfl-player-line${selected ? ' is-selected' : ''}`}
    aria-current={selected ? 'true' : undefined} onClick={onJump}>
    <span title={reference ? TARGETS_REFERENCE_NOTE : undefined}>{marketLabel(row.market)}{reference ? <small>reference</small> : item.rank !== null && <small>#{item.rank}</small>}</span>
    <span className={`nfl-player-num${isTd ? ' is-dim' : ''}`}>{isTd ? '--' : row.line?.toFixed(1) ?? '--'}</span>
    <span className="nfl-player-num">{formatProjection(row.market, row.projection)}</span>
    <span className={`nfl-player-num${isTd ? ' is-dim' : ''}`}>{reference ? `${edgeLabel(row.edge)} gap` : isTd ? books : edgePctLabel(item.edgeShare)}</span>
    <svg className="nfl-player-line__arrow" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" /></svg>
  </Link>
}

/** This week's full-game lines, ranked against the week-wide board; a row shows that prop's evidence below. */
export function NflPlayerLines({ week, isLoading, isError, otherMarkets }: { week: NflPlayerWeek | null, isLoading: boolean, isError: boolean, otherMarkets: string[] }) {
  const [params] = useSearchParams()
  const markets = week?.lines.map(item => item.row.market) ?? []
  const selectedMarket = selectedPropMarket(params, markets)
  const otherSelected = selectedMarket === null && selectedPropMarket(params, otherMarkets) !== null
  const selectedIndex = otherSelected ? -1 : selectedMarket === null ? 0 : markets.indexOf(selectedMarket)
  const opponent = week ? `${week.game.awayTeam} @ ${week.game.homeTeam} · ${formatKickoffTime(week.game.startUtc)}` : null
  return <section className="nfl-player-card" aria-label="This week's lines">
    <div className="nfl-player-card__head">
      <span className="nfl-player-label">This week's lines</span>
      {opponent && <span className="nfl-player-muted">{opponent}</span>}
    </div>
    {isLoading && <p className="nfl-player-card__empty">Loading this week's lines...</p>}
    {isError && <p className="nfl-player-card__empty">This week's lines could not be loaded.</p>}
    {!isLoading && !isError && week === null && <p className="nfl-player-card__empty">No lines stored for this player this week.</p>}
    {week && <div className="nfl-player-card__body">
      <div className="nfl-player-line is-head" aria-hidden="true">
        <span className="nfl-player-label">Market</span><span className="nfl-player-label">Line</span>
        <span className="nfl-player-label">Model</span><span className="nfl-player-label">Edge</span><span />
      </div>
      {week.lines.map((item, index) => <LineRow key={item.row.lineId} item={item} selected={index === selectedIndex} params={params}
        onJump={scrollToPropTabs} />)}
      <p className="nfl-player-note">Ranks and edges are read against the week's prop board. Edges are gray until the forward ranking check (27j) adopts a slice. Anytime TD shows the model beside the books, with no edge.</p>
    </div>}
  </section>
}
