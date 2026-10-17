import { Drawer } from 'antd'
import { useState } from 'react'
import NflEvidencePanel from '~/components/NflEvidencePanel'
import { useIsMobile } from '~/hooks/useIsMobile'
import { formatKickoffTime, formatProjection, marketLabel } from '~/utils/nflLabels'
import type { NflPlayerWeek, NflPlayerWeekLine } from '~/utils/nflPlayer'
import { edgePctLabel } from '~/utils/nflSignal'

const TD = 'anytime_touchdown'

function LineRow({ item, selected, onOpen }: { item: NflPlayerWeekLine, selected: boolean, onOpen: () => void }) {
  const { row } = item
  const isTd = row.market === TD
  // The de-vigged price where there is one, else the raw price, as the prop cards read it.
  const bookPrice = row.bookProbabilityDevigged ?? row.bookProbability
  const books = bookPrice === null ? 'no books' : `books ${formatProjection(TD, bookPrice)}`
  return <button type="button" className={`nfl-player-line${selected ? ' is-selected' : ''}`} onClick={onOpen}>
    <span>{marketLabel(row.market)}{item.rank !== null && <small>#{item.rank}</small>}</span>
    <span className={`nfl-player-num${isTd ? ' is-dim' : ''}`}>{isTd ? '--' : row.line?.toFixed(1) ?? '--'}</span>
    <span className="nfl-player-num">{formatProjection(row.market, row.projection)}</span>
    <span className={`nfl-player-num${isTd ? ' is-dim' : ''}`}>{isTd ? books : edgePctLabel(item.edgeShare)}</span>
    <span className="nfl-player-line__arrow" aria-hidden="true">›</span>
  </button>
}

/** This week's full-game lines, ranked against the week-wide board; a row opens the evidence panel. */
export function NflPlayerLines({ week, isLoading, isError }: { week: NflPlayerWeek | null, isLoading: boolean, isError: boolean }) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const isMobile = useIsMobile()
  const selected = week?.lines.find(item => item.row.lineId === selectedId) ?? null
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
      {week.lines.map(item => <LineRow key={item.row.lineId} item={item} selected={item.row.lineId === selectedId}
        onOpen={() => setSelectedId(item.row.lineId)} />)}
      <p className="nfl-player-note">Ranks and edges are read against the week's prop board. Edges are gray until the forward ranking check (27j) adopts a slice. Anytime TD shows the model beside the books, with no edge.</p>
    </div>}
    <Drawer open={selected !== null} onClose={() => setSelectedId(null)} width={isMobile ? '100%' : 460} title={null}
      className="nfl-slate nfl-player-drawer" destroyOnHidden>
      {selected && week && <NflEvidencePanel row={selected.row} game={week.game} alternates={selected.alternates} showPlayerLink={false} />}
    </Drawer>
  </section>
}
