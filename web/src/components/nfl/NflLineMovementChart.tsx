import type { NflGameDetail, NflLineHistory } from '~/types/nfl'
import { spreadLabel } from '~/utils/nflGameModel'
import { lineMovementChart } from '~/utils/nflLineMovement'

const MARKET_TITLES: Record<NflLineHistory['market'], string> = { spread: 'Spread', total: 'Total' }

/** The fields the chart reads, so the NBA game page can share it. */
type LineMovementGame = Pick<NflGameDetail, 'homeTeam' | 'awayTeam' | 'startUtc' | 'lineHistory'>

const DAY_FORMAT = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', weekday: 'short', hour: 'numeric' })

function lineText(history: NflLineHistory, line: number, detail: LineMovementGame): string {
  return history.market === 'spread' ? spreadLabel(line, detail.homeTeam, detail.awayTeam) : line.toFixed(1)
}

function moveCount(moves: number): string {
  return moves === 0 ? 'no moves' : `${moves} ${moves === 1 ? 'move' : 'moves'}`
}

function MarketPanel({ history, detail, now }: { history: NflLineHistory, detail: LineMovementGame, now: Date }) {
  const chart = lineMovementChart(history, detail.startUtc, now)
  if (chart === null) return null
  const opened = lineText(history, chart.open, detail)
  const current = lineText(history, chart.current, detail)
  return <figure className="nfl-line-panel">
    <figcaption>
      <span className="nfl-game-label">{MARKET_TITLES[history.market]}</span>
      <strong>{chart.move === 0 ? `${current}, no move` : `${opened} → ${current}`}</strong>
    </figcaption>
    <svg className="nfl-line-panel__plot" viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
      aria-label={`${MARKET_TITLES[history.market]} ${chart.move === 0 ? `held at ${current}` : `moved from ${opened} to ${current}`}`}>
      <polyline points={chart.points.map(({ x, y }) => `${x * 100},${y * 100}`).join(' ')} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
    <div className="nfl-line-panel__axis">
      <span>{DAY_FORMAT.format(chart.scale.tMin)}</span>
      <span>{history.book} · {moveCount(history.steps.length - 1)}</span>
      <span>{DAY_FORMAT.format(chart.scale.tMax)}</span>
    </div>
  </figure>
}

/** Pre-kickoff spread and total from one book per market; the spread reads by its favorite. */
export function NflLineMovementChart({ detail, now = new Date(), caveat = 'Before kickoff' }: { detail: LineMovementGame, now?: Date, caveat?: string }) {
  return <section className="nfl-game-card" aria-label="Line movement">
    <div className="nfl-game-card__head"><span className="nfl-game-label">Line movement</span><span className="nfl-game-caveat">{caveat}</span></div>
    {detail.lineHistory.length
      ? <div className="nfl-line-panels">{detail.lineHistory.map(history => <MarketPanel key={history.market} history={history} detail={detail} now={now} />)}</div>
      : <p className="nfl-game-note">No spread or total prices stored for this game yet.</p>}
  </section>
}
