import { useState } from 'react'
import type { SlateRow, TourTab } from '~/utils/tennisSlate'
import { TOUR_TABS, filterByTourTab, fmtEv, tableGroups } from '~/utils/tennisSlate'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtStartCT, fmtTournament } from '~/utils/format'

interface Props {
  rows: SlateRow[]
  /** Tournament headers; off for ranking sorts, where each row names its tournament. */
  grouped: boolean
  selectedKey: string | null
  onSelect: (key: string) => void
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

function SlateTableRow({ row, selected, showTournament, onSelect }: { row: SlateRow; selected: boolean; showTournament: boolean; onSelect: () => void }) {
  const pct = (value: number | null) => fmtPct(value)
  return (
    <tr
      className={`tennis-slate-table__row${selected ? ' is-selected' : ''}`}
      aria-selected={selected}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect() } }}
    >
      <StartCell startUtc={row.startUtc} />
      <td className="tennis-slate-table__players">
        <span>{row.players[0]}</span>
        <span>{row.players[1] ?? ''}</span>
        {showTournament && <small>{fmtTournament(row.tournament)}</small>}
      </td>
      <PairCell pair={row.elo} format={pct} extra />
      <PairCell pair={row.ml} format={pct} extra />
      <PairCell pair={row.market} format={pct} />
      <PairCell pair={row.model} format={pct} />
      <td className="tennis-slate-table__pick">{bestPickText(row)}</td>
      <td className={`tennis-slate-table__ev${row.primaryIsBestBet ? ' is-play' : ''}`}>{fmtEv(row.primaryPick ? row.primaryPick.evPct : row.primaryProp?.evPct)}</td>
      <PairCell pair={row.odds} format={(value) => fmtAmerican(value)} extra />
      <FlagsCell flags={row.flags} />
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

/** The day's matches grouped by tournament, in the page's sort order. */
export default function TennisSlateTable({ rows, grouped, selectedKey, onSelect }: Props) {
  const [tab, setTab] = useState<TourTab>('all')
  const groups = tableGroups(filterByTourTab(rows, tab), grouped)
  return (
    <section className="tennis-slate-table" aria-label="Today's tennis matches">
      <div className="tennis-slate-table__head">
        <h2 className="tennis-slate-section">All matches</h2>
        <TourTabs tab={tab} onChange={setTab} />
      </div>
      {groups.length === 0 ? (
        <div className="tennis-slate-table__empty">No matches in this group.</div>
      ) : (
        <div className="tennis-slate-table__scroll">
          <table>
            <thead>
              <tr>
                <th>Time</th><th>Match</th><th className="is-extra">ELO</th><th className="is-extra">ML</th><th>Market</th><th>Model</th>
                <th>Best pick</th><th>EV</th><th className="is-extra">Odds</th><th>Flags</th>
              </tr>
            </thead>
            {groups.map((group) => (
              <tbody key={group.tournament ?? 'ranked'}>
                {group.tournament != null && <tr className="tennis-slate-table__group"><td colSpan={10}>{fmtTournament(group.tournament)}</td></tr>}
                {group.rows.map((row) => (
                  <SlateTableRow key={row.key} row={row} selected={row.key === selectedKey} showTournament={!grouped} onSelect={() => onSelect(row.key)} />
                ))}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </section>
  )
}
