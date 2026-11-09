import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { SlateRow, TourTab } from '~/utils/tennisSlate'
import { TOUR_TABS, filterByTourTab, matchAnalysisPath, modelLeanCell, slateDayTime, tableGroups } from '~/utils/tennisSlate'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtTournament } from '~/utils/format'
import { tableCountPart } from '~/utils/slatePeriod'
// The table title is the game slates' window title.
import '~/pages/nfl-slate.css'

interface Props {
  rows: SlateRow[]
  /** Tournament headers; off for ranking sorts, where each row names its tournament. */
  grouped: boolean
  /** Quality flags are pipeline diagnostics: the owner's view only. */
  showFlags: boolean
  tab: TourTab
  onTabChange: (tab: TourTab) => void
  /** A command query searches the already-filtered slate across local tour tabs. */
  searchAllTabs?: boolean
  /** Every match on the day, before a search: the "of" in "3 of 20 matches". */
  total?: number
  emptyMessage?: string
}


const TAB_LABEL: Record<TourTab, string> = { all: 'All', ATP: 'ATP', WTA: 'WTA', CHALLENGER: 'Challenger', 'WTA 125': 'WTA 125' }

function PairCell({ pair, format, extra = false }: { pair: [number | null, number | null] | null; format: (value: number | null) => string; extra?: boolean }) {
  return (
    <td className={`tennis-slate-table__pair${extra ? ' is-extra' : ''}`}>
      <span>{format(pair?.[0] ?? null)}</span>
      <span>{format(pair?.[1] ?? null)}</span>
    </td>
  )
}

function StartCell({ startUtc }: { startUtc: string | null }) {
  const { day, time } = slateDayTime(startUtc, Date.now())
  return (
    <td className="tennis-slate-table__time">
      <span>{day}</span>
      <span>{time}</span>
    </td>
  )
}

/** Gray; only a priced best bet's EV is colored, as the EV column was. */
function LeanCell({ row }: { row: SlateRow }) {
  const { text, ev, link } = modelLeanCell(row)
  return (
    <td className="tennis-slate-table__pick">
      <span title={text}>{link ? <Link to={link}>{text}</Link> : text}</span>
      {ev !== null && <span className="tennis-slate-table__lean-ev">{ev} EV</span>}
    </td>
  )
}

function FlagsCell({ flags }: { flags: string[] }) {
  const labels = flags.map((flag) => flag.replaceAll('_', ' '))
  return (
    <td className="tennis-slate-table__flags" title={labels.join(', ') || undefined}>
      {labels[0] && <span>{labels[0]}</span>}
      {labels.length > 1 && <span>+{labels.length - 1}</span>}
    </td>
  )
}

function SlateTableRow({ row, showTournament, showFlags }: { row: SlateRow; showTournament: boolean; showFlags: boolean }) {
  const navigate = useNavigate()
  const analysisPath = matchAnalysisPath(row.match)
  const pct = (value: number | null) => fmtPct(value)
  const matchup = row.players[1] ? `${row.players[0]} vs ${row.players[1]}` : row.players[0]
  // Links keep native keyboard and modified-click behavior.
  function onRowClick(event: MouseEvent<HTMLTableRowElement>) {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    if ((event.target as HTMLElement).closest('a, button')) return
    if (analysisPath) navigate(analysisPath)
  }
  return (
    <tr className="tennis-slate-table__row" onClick={onRowClick}>
      <StartCell startUtc={row.startUtc} />
      <td className="tennis-slate-table__players">
        {analysisPath ? <Link
          to={analysisPath}
          className="tennis-slate-table__toggle"
          aria-label={`${matchup}, open match analysis`}
        >
          <span>{row.players[0]}</span>
          <span>{row.players[1] ?? ''}</span>
        </Link> : <span className="tennis-slate-table__toggle">
          <span>{row.players[0]}</span>
          <span>{row.players[1] ?? ''}</span>
        </span>}
        {showTournament && <small>{fmtTournament(row.tournament)}</small>}
      </td>
      <PairCell pair={row.elo} format={pct} extra />
      <PairCell pair={row.ml} format={pct} extra />
      <PairCell pair={row.market} format={pct} />
      <PairCell pair={row.model} format={pct} />
      <LeanCell row={row} />
      <PairCell pair={row.odds} format={(value) => fmtAmerican(value)} extra />
      {showFlags && <FlagsCell flags={row.flags} />}
    </tr>
  )
}

function TourTabs({ tab, onChange }: { tab: TourTab; onChange: (tab: TourTab) => void }) {
  return (
    <div className="tennis-slate-tabs" role="tablist" aria-label="Tour">
      {TOUR_TABS.map((value) => (
        <button key={value} type="button" role="tab" aria-selected={tab === value} className={tab === value ? 'is-active' : ''} onClick={() => onChange(value)}>
          {TAB_LABEL[value]}
        </button>
      ))}
    </div>
  )
}

/** Each canonical match links to its analysis page (F-43). */
export default function TennisSlateTable({ rows, grouped, showFlags, tab, onTabChange, searchAllTabs = false, total, emptyMessage = 'No matches in this group.' }: Props) {
  const groups = tableGroups(searchAllTabs ? rows : filterByTourTab(rows, tab), grouped)
  const columns = showFlags ? 9 : 8
  const shown = groups.reduce((sum, group) => sum + group.rows.length, 0)
  const count = tableCountPart(shown, searchAllTabs ? total ?? shown : shown, searchAllTabs, 'match', 'matches')
  return (
    <section className="tennis-slate-table" aria-label="Today's tennis matches">
      <div className="tennis-slate-table__head">
        <h2 className="nfl-slate-window__title tennis-slate-table__title">All matches <small>{count}</small></h2>
        <TourTabs tab={tab} onChange={onTabChange} />
      </div>
      {groups.length === 0 ? (
        <div className="tennis-slate-table__empty">{emptyMessage}</div>
      ) : (
        <div className="tennis-slate-table__scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th><th>Match</th><th className="is-extra">ELO</th><th className="is-extra">ML</th><th>Market</th><th>Model</th>
                <th>Model lean</th><th className="is-extra">Odds</th>{showFlags && <th>Flags</th>}
              </tr>
            </thead>
            {groups.map((group) => (
              <tbody key={group.tournament ?? 'ranked'}>
                {group.tournament != null && <tr className="tennis-slate-table__group"><td colSpan={columns}>{fmtTournament(group.tournament)}</td></tr>}
                {group.rows.map((row) => (
                  <SlateTableRow key={row.key} row={row} showTournament={!grouped} showFlags={showFlags} />
                ))}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </section>
  )
}
