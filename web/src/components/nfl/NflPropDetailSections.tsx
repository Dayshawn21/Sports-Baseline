import { Tag, Tooltip } from 'antd'
import type { CSSProperties } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { NflHistorySample, NflSlateLine } from '~/types/nfl'
import { FORM_PARAM, formBarLabel, formEmptyText, formHistoryDate, formOptions, formSample, formShortNote, formTitle, parseFormWindow, resolveFormWindow, type FormRow, type FormWindow } from '~/utils/nflFormWindow'
import { formatProjection } from '~/utils/nflLabels'
import { formBars, type NflRecentBar } from '~/utils/nflPropCards'
import { history, type NflDetailHistory, type NflPropDetailModel } from '~/utils/nflPropDetail'
import { playerSearch } from '~/utils/nflPlayer'
import { volumeReferenceModel } from '~/utils/nflVolume'
import './nfl-prop-detail.css'

export function DetailProjection({ detail }: { detail: NflPropDetailModel }) {
  const tone = !detail.hasEdge ? '' : detail.isUnder ? ' is-under' : ' is-over'
  return <section className="nfl-prop-detail__projection">
    <span>{detail.projectionLabel}</span>
    <strong>{detail.projectionText}</strong>
    <p className={`nfl-prop-detail__delta${tone}`}>{detail.deltaText}</p>
  </section>
}

/** Where zero sits in a plot that reaches below it: a bar's bottom edge if it is not negative, else its top edge. */
function zeroPct(bar: NflRecentBar): number {
  return bar.value < 0 ? (bar.bottomPct ?? 0) + bar.heightPct : bar.bottomPct ?? 0
}

/** `seasonStartMonth` is the 0-based month a new season-year begins, for the year under an older game's date; NFL's by default. */
export function GameLogBars({ row, sample, seasonStartMonth }: { row: Parameters<typeof formBars>[1], sample: NflHistorySample, seasonStartMonth?: number }) {
  const { bars, linePct } = formBars(sample, row)
  const now = new Date()
  if (!bars.length) return null
  const signed = bars[0].bottomPct !== undefined
  const style = { ...(linePct === null ? {} : { '--line': `${linePct}%` }), ...(signed ? { '--zero': `${zeroPct(bars[0])}%` } : {}) } as CSSProperties
  return <div className="nfl-prop-detail__chart" aria-label={`${bars.length} games against the line`}>
    <div className="nfl-prop-detail__plot" style={style}>
      {signed && <span className="nfl-prop-detail__zero" />}
      {linePct !== null && <span className="nfl-prop-detail__line-mark" />}
      {bars.map((bar, index) => <div key={index} className={`nfl-prop-detail__col is-${bar.vsLine ?? 'none'}`}
        style={{ '--h': `${bar.heightPct}%`, ...(bar.bottomPct === undefined ? {} : { '--b': `${bar.bottomPct}%` }) } as CSSProperties}>
        <span className="nfl-prop-detail__val">{formBarLabel(bar.value)}</span>
        <span className="nfl-prop-detail__bar" />
      </div>)}
    </div>
    <div className="nfl-prop-detail__opps">{bars.map((bar, index) => {
      const date = formHistoryDate(bar.gameDate, now, seasonStartMonth)
      return <span key={index}>{bar.opponentTeam ?? '--'}
        {date && <small title={`${date.month} ${date.day}${date.year ? ` ${date.year}` : ''}`}>{date.month}<br />{date.day}{date.year && <><br />{date.year}</>}</small>}
      </span>
    })}</div>
  </div>
}

export function FormSwitch({ row, window }: { row: FormRow, window: FormWindow }) {
  const [params, setParams] = useSearchParams()
  const choose = (next: FormWindow) => setParams(playerSearch(params, { [FORM_PARAM]: next === '5' ? null : next }), { replace: true })
  return <div className="nfl-prop-detail__switch" role="group" aria-label="Recent form window">
    {formOptions(row).map(option => <button key={option.window} type="button" aria-pressed={option.window === window}
      disabled={option.disabledReason !== null} title={option.disabledReason ?? undefined} onClick={() => choose(option.window)}>{option.label}</button>)}
  </div>
}

/** Bars only where a game is a count against a full-game line; a TD game is 0 or 1, so TD keeps the text list. */
export function DetailGameLog({ row }: { row: NflSlateLine }) {
  const [params] = useSearchParams()
  const window = resolveFormWindow(row, parseFormWindow(params))
  const sample = formSample(row, window)
  const form = history(formTitle(row, window), row.market, sample, new Date())
  const note = formShortNote(row, window)
  const bars = formBars(sample, row).bars.length > 0
  return <section className="nfl-prop-detail__section">
    <div className="nfl-prop-detail__section-head">
      <h3>{form.title}</h3>
      <span>{sample.average === null ? formEmptyText(row, window) : note ? `${formatProjection(row.market, sample.average)} avg · ${note}` : form.value}</span>
    </div>
    <div className="nfl-prop-detail__toolbar">
      <FormSwitch row={row} window={window} />
      {bars && row.line !== null && row.segment === 'full_game' && <span className="nfl-prop-detail__legend">Line {row.line.toFixed(1)}</span>}
    </div>
    <GameLogBars row={row} sample={sample} />
    {!bars && form.games.length > 0 && <ul className="nfl-prop-detail__list nfl-prop-detail__games" aria-label={form.title}>{form.games.map((game, index) => <li key={index}>{game}</li>)}</ul>}
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
      {detail.breakdown.map(item => <div key={item.label} className={item.label === 'Projection' || item.label === 'Reference' ? 'is-total' : undefined}>
        <dt>{item.label}{item.note && <small>{item.note}</small>}</dt>
        <dd>{item.value}</dd>
      </div>)}
    </dl>
  </section>
}

export function DetailVolume({ row }: { row: NflSlateLine }) {
  const volume = volumeReferenceModel(row)
  if (volume === null) return null
  return <section className="nfl-prop-detail__section nfl-prop-detail__volume">
    <SectionHead title={volume.title} aside={volume.aside} />
    <dl className="nfl-prop-detail__kv">{volume.rows.map(item => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>
    <p className="nfl-prop-detail__note">{volume.note}</p>
  </section>
}

export function DetailLines({ detail }: { detail: NflPropDetailModel }) {
  return <section className="nfl-prop-detail__section">
    <SectionHead title="PrizePicks lines" />
    <table className="nfl-prop-detail__table">
      <thead><tr><th>Type</th><th>Line</th>{!detail.referenceNote && <th>P(over)</th>}</tr></thead>
      <tbody>{detail.lines.map(line => <tr key={line.key} className={line.selected ? 'is-selected' : undefined}>
        <td><Tag color={line.typeColor}>{line.typeLabel}</Tag>{line.selected && <span className="nfl-prop-detail__this">This line</span>}</td>
        <td>{line.lineText}</td>
        {!detail.referenceNote && <td>{line.pOverText ?? '--'}</td>}
      </tr>)}</tbody>
    </table>
    {detail.pOverNote && <Tooltip title={P_OVER_NOTE}><p className="nfl-prop-detail__note">{detail.pOverNote}</p></Tooltip>}
    {detail.referenceNote && <p className="nfl-prop-detail__note">{detail.referenceNote}</p>}
  </section>
}

export function DetailSportsbook({ detail }: { detail: NflPropDetailModel }) {
  if (detail.sportsbook === null) return null
  return <section className="nfl-prop-detail__section">
    <SectionHead title="Sportsbooks" aside={detail.sportsbook.summary} />
    <p className="nfl-prop-detail__list">{detail.sportsbook.comparison}</p>
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
