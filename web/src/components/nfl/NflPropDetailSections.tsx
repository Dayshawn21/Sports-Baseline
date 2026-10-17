import { Tag, Tooltip } from 'antd'
import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import type { NflSlateLine } from '~/types/nfl'
import { NFL_GAME_MODEL_CAVEAT } from '~/utils/nflGameModel'
import { formatHistoryValue } from '~/utils/nflLabels'
import { recentBars } from '~/utils/nflPropCards'
import type { NflDetailHistory, NflPropDetailModel } from '~/utils/nflPropDetail'
import './nfl-prop-detail.css'

export function DetailHeader({ detail, playerLink }: { detail: NflPropDetailModel, playerLink: string | null }) {
  return <div className="nfl-prop-detail__player">
    <span className="nfl-prop-detail__badge" aria-hidden="true">{detail.badge}</span>
    <div>
      <h2>{playerLink ? <Link className="nfl-prop-detail__player-link" to={playerLink}>{detail.playerName}</Link> : detail.playerName}</h2>
      <p>{detail.meta}</p>
    </div>
  </div>
}

export function DetailProjection({ detail }: { detail: NflPropDetailModel }) {
  const tone = !detail.hasEdge ? '' : detail.isUnder ? ' is-under' : ' is-over'
  return <section className="nfl-prop-detail__projection">
    <span>{detail.projectionLabel}</span>
    <strong>{detail.projectionText}</strong>
    <p className={`nfl-prop-detail__delta${tone}`}>{detail.deltaText}</p>
  </section>
}

function GameLogBars({ row }: { row: NflSlateLine }) {
  const { bars, linePct } = recentBars(row)
  if (!bars.length) return null
  const style = linePct === null ? undefined : { '--line': `${linePct}%` } as CSSProperties
  return <div className="nfl-prop-detail__chart" aria-label={`Last ${bars.length} games against the line`}>
    <div className="nfl-prop-detail__plot" style={style}>
      {linePct !== null && <span className="nfl-prop-detail__line-mark"><span>{row.line?.toFixed(1)}</span></span>}
      {bars.map((bar, index) => <div key={index} className={`nfl-prop-detail__col is-${bar.vsLine ?? 'none'}`} style={{ '--h': `${bar.heightPct}%` } as CSSProperties}>
        <span className="nfl-prop-detail__val">{formatHistoryValue(row.market, bar.value)}</span>
        <span className="nfl-prop-detail__bar" />
      </div>)}
    </div>
    <div className="nfl-prop-detail__opps">{bars.map((bar, index) => <span key={index}>{bar.opponentTeam ?? '--'}</span>)}</div>
  </div>
}

/** Bars only where a game is a count against a full-game line; a TD game is 0 or 1, so TD keeps the text list. */
export function DetailGameLog({ row, detail }: { row: NflSlateLine, detail: NflPropDetailModel }) {
  const bars = recentBars(row).bars.length > 0
  return <section className="nfl-prop-detail__section">
    <div className="nfl-prop-detail__section-head">
      <h3>{detail.recentForm.title}</h3>
      <span>{detail.recentForm.value}</span>
    </div>
    <GameLogBars row={row} />
    {!bars && detail.recentForm.detail && <p className="nfl-prop-detail__list">{detail.recentForm.detail}</p>}
  </section>
}

const P_OVER_NOTE = 'Fitted on 2025 results for this market. Display only: it does not change the edge or rank.'

function SectionHead({ title, aside }: { title: string, aside?: string }) {
  return <div className="nfl-prop-detail__section-head"><h3>{title}</h3>{aside && <span>{aside}</span>}</div>
}

function HistoryItem({ item }: { item: NflDetailHistory }) {
  return <div className="nfl-prop-detail__history">
    <SectionHead title={item.title} aside={item.value} />
    {item.detail && <p className="nfl-prop-detail__list">{item.detail}</p>}
  </div>
}

export function DetailContext({ detail }: { detail: NflPropDetailModel }) {
  return <section className="nfl-prop-detail__section nfl-prop-detail__context">
    {detail.context.map(item => <HistoryItem key={item.title} item={item} />)}
  </section>
}

export function DetailBreakdown({ detail }: { detail: NflPropDetailModel }) {
  return <section className="nfl-prop-detail__section">
    <SectionHead title="How the projection is built" />
    <p className="nfl-prop-detail__why">{detail.why}</p>
    <dl className="nfl-prop-detail__rows">
      {detail.breakdown.map(item => <div key={item.label} className={item.label === 'Projection' ? 'is-total' : undefined}>
        <dt>{item.label}{item.note && <small>{item.note}</small>}</dt>
        <dd>{item.value}</dd>
      </div>)}
    </dl>
  </section>
}

export function DetailLines({ detail }: { detail: NflPropDetailModel }) {
  return <section className="nfl-prop-detail__section">
    <SectionHead title="PrizePicks lines" />
    <table className="nfl-prop-detail__table">
      <thead><tr><th>Type</th><th>Line</th><th>P(over)</th></tr></thead>
      <tbody>{detail.lines.map(line => <tr key={line.key} className={line.selected ? 'is-selected' : undefined}>
        <td><Tag color={line.typeColor}>{line.typeLabel}</Tag>{line.selected && <span className="nfl-prop-detail__this">This line</span>}</td>
        <td>{line.lineText}</td>
        <td>{line.pOverText ?? '--'}</td>
      </tr>)}</tbody>
    </table>
    {detail.pOverNote && <Tooltip title={P_OVER_NOTE}><p className="nfl-prop-detail__note">{detail.pOverNote}</p></Tooltip>}
  </section>
}

export function DetailSportsbook({ detail }: { detail: NflPropDetailModel }) {
  if (detail.sportsbook === null) return null
  return <section className="nfl-prop-detail__section">
    <SectionHead title="Sportsbooks" aside={detail.sportsbook.summary} />
    <p className="nfl-prop-detail__list">{detail.sportsbook.comparison}</p>
  </section>
}

/** `gameLink` is the game page's path, or null where the reader is already on it. */
export function DetailGameMarket({ detail, gameLink }: { detail: NflPropDetailModel, gameLink: string | null }) {
  const market = detail.gameMarket
  return <section className="nfl-prop-detail__section">
    <SectionHead title="Game market" aside={market?.book} />
    {market === null ? <p className="nfl-prop-detail__list">No game market</p> : <>
      <dl className="nfl-prop-detail__kv">{market.rows.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
      {market.modelText && <Tooltip title={NFL_GAME_MODEL_CAVEAT}><p className="nfl-prop-detail__model"><span>Model · not a pick</span><span>{market.modelText}</span></p></Tooltip>}
    </>}
    {gameLink && <Link className="nfl-prop-detail__game-link" to={gameLink}>Open game page →</Link>}
  </section>
}

export function DetailStatus({ detail }: { detail: NflPropDetailModel }) {
  return <section className="nfl-prop-detail__section">
    <SectionHead title="Status" />
    <dl className="nfl-prop-detail__kv">{detail.status.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
  </section>
}

export function DetailFlags({ detail }: { detail: NflPropDetailModel }) {
  if (!detail.flags.length) return null
  return <section className="nfl-prop-detail__section">
    <SectionHead title="Quality notes" />
    <div className="nfl-prop-detail__flags">{detail.flags.map(flag => <Tooltip key={flag.key} title={flag.tooltip}><Tag>{flag.label}</Tag></Tooltip>)}</div>
  </section>
}
