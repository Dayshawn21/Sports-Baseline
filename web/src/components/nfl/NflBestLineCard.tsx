import type { NflBestLine } from '~/types/nfl'
import { nflBestLineRows, type NflBestLineSideRow } from '~/utils/nflBestLine'

function Side({ row }: { row: NflBestLineSideRow }) {
  return <div>
    <span className="nfl-game-bl__price"><b>{row.label}</b> {row.price}</span>
    <small>{row.book} · {row.age}</small>
    {row.vsFair !== null && <small>{row.vsFair}</small>}
  </div>
}

/** Each side's best price across books beside the fair price. Gray only: a reference, never a pick. */
export function NflBestLineCard({ bestLine, homeTeam, awayTeam, now = new Date() }: {
  bestLine: NflBestLine | null, homeTeam: string, awayTeam: string, now?: Date,
}) {
  return <section className="nfl-game-card" aria-label="Best line">
    <div className="nfl-game-card__head"><span className="nfl-game-label">Best line</span><span className="nfl-game-caveat">Reference, not a pick</span></div>
    {bestLine === null
      ? <p className="nfl-game-note">No book prices fetched in the last 36 hours.</p>
      : <>
        <div className="nfl-game-bl">
          <div /><div className="nfl-game-label is-span">Best price</div><div className="nfl-game-label">Fair</div>
          {nflBestLineRows(bestLine, homeTeam, awayTeam, now).map(row => <div key={row.market} className="nfl-game-bl__row">
            <div className="nfl-game-label">{row.market}</div>
            {row.sides.map(side => <Side key={side.label} row={side} />)}
            <div className="is-fair">
              {row.fair === null ? <small>No fair price</small> : <>
                <span className="nfl-game-bl__price">{row.fair.label}</span>
                <small>{row.fair.source} · {row.fair.age}</small>
              </>}
            </div>
          </div>)}
        </div>
        <p className="nfl-game-note">Best price across the stored books; fair is Pinnacle de-vigged, or the books' consensus without it. Prices older than {bestLine.maxAgeHours} hours are left out.</p>
      </>}
  </section>
}
