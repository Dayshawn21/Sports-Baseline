import type { LineMovementGame, LineMovementHistory } from '~/types/lineMovement'
import { spreadLabel } from '~/utils/nflGameModel'
import { lineMovementChart } from '~/utils/nflLineMovement'

const DAY_FORMAT = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Chicago', weekday: 'short', hour: 'numeric' })

function lineText(history: LineMovementHistory, line: number, detail: LineMovementGame): string {
  return history.market === 'spread' ? spreadLabel(line, detail.homeTeam, detail.awayTeam) : line.toFixed(1)
}

function moveCount(moves: number): string {
  return moves === 0 ? 'no moves' : `${moves} ${moves === 1 ? 'move' : 'moves'}`
}

function MarketPanel({ history, detail, now, title }: { history: LineMovementHistory, detail: LineMovementGame, now: Date, title: string }) {
  const chart = lineMovementChart(history, detail.startUtc, now)
  if (chart === null) return null
  const opened = lineText(history, chart.open, detail)
  const current = lineText(history, chart.current, detail)
  return <figure className="nfl-line-panel">
    <figcaption>
      <span className="nfl-game-label">{title} (CT)</span>
      <strong>{chart.move === 0 ? `${current}, no move` : `${opened} → ${current}`}</strong>
    </figcaption>
    <svg className="nfl-line-panel__plot" viewBox="0 0 100 100" preserveAspectRatio="none" role="img"
      aria-label={`${title} ${chart.move === 0 ? `held at ${current}` : `moved from ${opened} to ${current}`}`}>
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
export function NflLineMovementChart({
  detail, now = new Date(), caveat = 'Before kickoff', spreadTitle = 'Spread',
  emptyMessage = 'No spread or total prices stored for this game yet.',
}: { detail: LineMovementGame, now?: Date, caveat?: string, spreadTitle?: string, emptyMessage?: string }) {
  const histories = detail.lineHistory.filter(history => history.steps.length > 0)
  return <section className="nfl-game-card" aria-label="Line movement">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">Line movement</h2><span className="nfl-game-caveat">{caveat}</span></div>
    {histories.length
      ? <div className="nfl-line-panels">{histories.map(history => <MarketPanel key={history.market} history={history} detail={detail} now={now} title={history.market === 'spread' ? spreadTitle : 'Total'} />)}</div>
      : <p className="nfl-game-note">{emptyMessage}</p>}
  </section>
}
