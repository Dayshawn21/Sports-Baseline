import { Fragment } from 'react'
import type { MouseEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import TennisMatchDetail from '~/components/tennis/TennisMatchDetail'
import type { SlateRow, TourTab } from '~/utils/tennisSlate'
import { TOUR_TABS, filterByTourTab, fmtEv, matchAnalysisPath, tableGroups } from '~/utils/tennisSlate'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtStartCT, fmtTournament } from '~/utils/format'
import { propMatchPath } from '~/utils/tennisMatchView'

interface Props {
  rows: SlateRow[]
  /** Tournament headers; off for ranking sorts, where each row names its tournament. */
  grouped: boolean
  /** The one row whose detail is open, or null. */
  expandedKey: string | null
  onToggle: (key: string) => void
  /** Quality flags are pipeline diagnostics: the owner's view only. */
  showFlags: boolean
  /** Lifted to the page so a digest pick can switch to a tab that shows its row. */
  tab: TourTab
  onTabChange: (tab: TourTab) => void
  /** A command query searches the already-filtered slate across local tour tabs. */
  searchAllTabs?: boolean
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

function bestPickText(row: SlateRow): string {
  if (row.primaryPick) return row.primaryPick.pick
  if (row.primaryProp) return `${row.primaryProp.playerName ?? 'Player'} · ${row.primaryProp.statType}`
  return '—'
}

function StartCell({ startUtc }: { startUtc: string | null }) {
  const [day, time] = (fmtStartCT(startUtc) ?? 'TBA').split(' · ')
  return (
    <td className="tennis-slate-table__time">
      <span>{time ? day : ''}</span>
      <span>{time ?? day}</span>
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

function detailId(key: string): string {
  return `tennis-match-detail-${key}`
}

function SlateTableRow({ row, open, showTournament, showFlags, onToggle }: { row: SlateRow; open: boolean; showTournament: boolean; showFlags: boolean; onToggle: () => void }) {
  const navigate = useNavigate()
  const analysisPath = matchAnalysisPath(row.match)
  const propPath = row.primaryProp ? propMatchPath(row.primaryProp) : null
  const pct = (value: number | null) => fmtPct(value)
  const matchup = row.players[1] ? `${row.players[0]} vs ${row.players[1]}` : row.players[0]
  // Links keep native keyboard and modified-click behavior.
  function onRowClick(event: MouseEvent<HTMLTableRowElement>) {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    if ((event.target as HTMLElement).closest('a, button')) return
    if (analysisPath) navigate(analysisPath)
    else onToggle()
  }
  return (
    <tr className={`tennis-slate-table__row${open ? ' is-open' : ''}`} onClick={onRowClick}>
      <StartCell startUtc={row.startUtc} />
      <td className="tennis-slate-table__players">
        {analysisPath ? <Link
          to={analysisPath}
          className="tennis-slate-table__toggle"
          data-match-key={row.key}
          aria-label={`${matchup}, open match analysis`}
        >
          <span>{row.players[0]}</span>
          <span>{row.players[1] ?? ''}</span>
        </Link> : <button
          type="button"
          className="tennis-slate-table__toggle"
          data-match-key={row.key}
          aria-expanded={open}
          aria-controls={open ? detailId(row.key) : undefined}
          aria-label={`${matchup}, show match detail`}
          onClick={onToggle}
        >
          <span>{row.players[0]}</span>
          <span>{row.players[1] ?? ''}</span>
        </button>}
        {showTournament && <small>{fmtTournament(row.tournament)}</small>}
      </td>
      <PairCell pair={row.elo} format={pct} extra />
      <PairCell pair={row.ml} format={pct} extra />
      <PairCell pair={row.market} format={pct} />
      <PairCell pair={row.model} format={pct} />
      <td className="tennis-slate-table__pick"><span>{!row.primaryPick && propPath
        ? <Link to={propPath}>{bestPickText(row)}</Link> : bestPickText(row)}</span></td>
      <td className={`tennis-slate-table__ev${row.primaryIsBestBet ? ' is-play' : ''}`}>{fmtEv(row.primaryPick ? row.primaryPick.evPct : row.primaryProp?.evPct)}</td>
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

function DetailRow({ row, columns, showFlags }: { row: SlateRow; columns: number; showFlags: boolean }) {
  return (
    <tr className="tennis-slate-table__detail" id={detailId(row.key)}>
      <td colSpan={columns}>
        <div className="tennis-match-detail"><TennisMatchDetail match={row.match} showFlags={showFlags} /></div>
      </td>
    </tr>
  )
}

/** Canonical matches link to analysis; unlinked props keep their inline detail. */
export default function TennisSlateTable({ rows, grouped, expandedKey, onToggle, showFlags, tab, onTabChange, searchAllTabs = false, emptyMessage = 'No matches in this group.' }: Props) {
  const groups = tableGroups(searchAllTabs ? rows : filterByTourTab(rows, tab), grouped)
  const columns = showFlags ? 10 : 9
  return (
    <section className="tennis-slate-table" aria-label="Today's tennis matches">
      <div className="tennis-slate-table__head">
        <h2 className="tennis-slate-section">All matches</h2>
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
                <th>Best pick</th><th>EV</th><th className="is-extra">Odds</th>{showFlags && <th>Flags</th>}
              </tr>
            </thead>
            {groups.map((group) => (
              <tbody key={group.tournament ?? 'ranked'}>
                {group.tournament != null && <tr className="tennis-slate-table__group"><td colSpan={columns}>{fmtTournament(group.tournament)}</td></tr>}
                {group.rows.map((row) => {
                  const open = matchAnalysisPath(row.match) == null && row.key === expandedKey
                  return (
                    <Fragment key={row.key}>
                      <SlateTableRow row={row} open={open} showTournament={!grouped} showFlags={showFlags} onToggle={() => onToggle(row.key)} />
                      {open && <DetailRow row={row} columns={columns} showFlags={showFlags} />}
                    </Fragment>
                  )
                })}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </section>
  )
}
