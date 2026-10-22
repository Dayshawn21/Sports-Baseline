import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { NflGameNotes, NflNoteInjury, NflTeamForm } from '~/types/nfl'
import { depthLabel, injuryLabel, injuryTag } from '~/utils/nflAvailability'
import { formLabel, injuriesByTeam, injuryGroups, restLabel } from '~/utils/nflGameNotes'
import { fmtDateCT, fmtTimeCT } from '~/utils/format'

const CHANGE_LABELS = { promoted: 'Up', demoted: 'Down', new: 'New' } as const
const STATUS_CLASSES: Record<string, string> = { Out: 'is-out', Doubtful: 'is-caution', Questionable: 'is-caution' }

function Card({ title, meta, children }: { title: string, meta?: string, children: ReactNode }) {
  return <section className="nfl-game-card">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">{title}</h2>{meta && <span className="nfl-game-side__meta">{meta}</span>}</div>
    <div className="nfl-game-side__body">{children}</div>
  </section>
}

function Empty({ text }: { text: string }) {
  return <p className="nfl-game-side__empty">{text}</p>
}

function InjuryRow({ row }: { row: NflNoteInjury }) {
  const tag = injuryTag(row.injuryStatus)
  const playerLink = ['QB', 'RB', 'WR', 'TE', 'K', 'P'].includes(row.position)
  return <li className="nfl-game-side__row">
    <span className="nfl-game-side__team">{row.team}</span>
    <span className="nfl-game-side__who"><b>{playerLink ? <Link to={`/nfl/player/${row.playerId}`}>{row.playerName}</Link> : row.playerName}</b><small>{row.position} · {injuryLabel(row)}</small><small>{row.updatedAt && fmtDateCT(row.updatedAt) ? `Stored ${fmtDateCT(row.updatedAt)} · ${fmtTimeCT(row.updatedAt)}` : 'Stored update time unavailable'}</small></span>
    <span className={`nfl-game-tag ${row.injuryStatus ? STATUS_CLASSES[row.injuryStatus] ?? '' : ''}`}>{tag?.label ?? 'Practice'}</span>
  </li>
}

function Injuries({ notes }: { notes: NflGameNotes }) {
  const rows = injuriesByTeam(notes.injuries, notes.awayTeam, notes.homeTeam).flatMap(([, teamRows]) => teamRows)
  return <Card title="Injury report" meta="All positions · NFLverse">
    {rows.length ? injuryGroups(rows).map(group => <details className="nfl-game-injury-group" key={group.label} open>
      <summary>{group.label} <span>{group.rows.length}</span></summary>
      <ul className="nfl-game-side__list">{group.rows.map(row => <InjuryRow key={`${row.team}-${row.playerId}`} row={row} />)}</ul>
    </details>) : <Empty text="No report entries stored for either team." />}
    <p className="nfl-game-injury-note">Stored updates show when rows were loaded, not the official report time. Missing entries do not confirm availability. Full-practice-only entries are omitted.</p>
  </Card>
}

function DepthChanges({ notes }: { notes: NflGameNotes }) {
  return <Card title="Depth changes">
    {notes.depthChanges.length ? <ul className="nfl-game-side__list">{notes.depthChanges.map(row => <li key={`${row.team}-${row.playerName}`} className="nfl-game-side__row">
      <span className="nfl-game-side__team">{row.team}</span>
      <span className="nfl-game-side__who"><b><Link to={`/nfl/player/${row.playerId}`}>{row.playerName}</Link></b><small>{depthLabel(row)}</small></span>
      <span className="nfl-game-tag">{CHANGE_LABELS[row.change]}</span>
    </li>)}</ul> : <Empty text="No starter or backup changes" />}
  </Card>
}

export function NflGameAvailability({ notes, isLoading, isError }: { notes: NflGameNotes | undefined, isLoading: boolean, isError: boolean }) {
  return <section className="nfl-game-availability" aria-label="Player availability">
    {notes ? <details>
      <summary><span>Player availability</span><small>{notes.injuries.length} on injury report · {notes.depthChanges.length} depth changes</small></summary>
      <div className="nfl-game-availability__body"><Injuries notes={notes} /><DepthChanges notes={notes} /></div>
      <p className="nfl-game-note">Display context only. These reports do not change projections or ranks.</p>
    </details> : <p className="nfl-game-availability__status">{isLoading ? 'Loading player availability...' : isError ? 'Player availability could not load. Check the latest team reports before using these comparisons.' : 'No player availability notes stored for this game.'}</p>}
  </section>
}

function FormRow({ form }: { form: NflTeamForm }) {
  const rest = restLabel(form)
  return <div className="nfl-game-side__form">
    <span className="nfl-game-side__who"><b>{form.team}</b>{rest && <small className={form.shortWeek ? 'is-short' : ''}>{rest}</small>}</span>
    {form.recent.length ? <ul>{form.recent.map(game => <li key={game.week}><small>Wk {game.week}</small>{formLabel(game)}</li>)}</ul> : <Empty text="No completed games this season" />}
  </div>
}

/** Item 29/30 game notes as sidebar cards. Context only: never changes an edge or its rank. */
export function NflGameSidebar({ notes, isLoading, isError }: { notes: NflGameNotes | undefined, isLoading: boolean, isError: boolean }) {
  if (isLoading) return <aside className="nfl-game-side"><Card title="Game notes"><Empty text="Loading injuries, depth and team stats..." /></Card></aside>
  if (isError || !notes) return <aside className="nfl-game-side"><Card title="Game notes"><Empty text={isError ? 'Game notes are unavailable right now.' : 'No notes stored for this game.'} /></Card></aside>
  return <aside className="nfl-game-side" aria-label="Game notes">
    <div className="nfl-game-side__availability"><Injuries notes={notes} /><DepthChanges notes={notes} /></div>
    <Card title="Form and rest"><FormRow form={notes.awayForm} /><FormRow form={notes.homeForm} /></Card>
    <p className="nfl-game-note is-inline">Context only. Injuries, depth, form and team stats never change an edge or its rank.</p>
  </aside>
}
