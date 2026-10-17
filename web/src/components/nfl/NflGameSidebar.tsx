import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { NflGameNotes, NflNoteInjury, NflTeamForm, NflTeamStats } from '~/types/nfl'
import { depthLabel, injuryLabel, injuryTag } from '~/utils/nflAvailability'
import { SMALL_SAMPLE_GAMES, TEAM_STAT_ROWS, formLabel, gamesLabel, injuriesByTeam, rankLabel, restLabel, statValue } from '~/utils/nflGameNotes'

const CHANGE_LABELS = { promoted: 'Up', demoted: 'Down', new: 'New' } as const
const STATUS_CLASSES: Record<string, string> = { Out: 'is-out', Doubtful: 'is-caution', Questionable: 'is-caution' }

function Card({ title, meta, children }: { title: string, meta?: string, children: ReactNode }) {
  return <section className="nfl-game-card">
    <div className="nfl-game-card__head"><span className="nfl-game-label">{title}</span>{meta && <span className="nfl-game-side__meta">{meta}</span>}</div>
    <div className="nfl-game-side__body">{children}</div>
  </section>
}

function Empty({ text }: { text: string }) {
  return <p className="nfl-game-side__empty">{text}</p>
}

function InjuryRow({ row }: { row: NflNoteInjury }) {
  const tag = injuryTag(row.injuryStatus)
  return <li className="nfl-game-side__row">
    <span className="nfl-game-side__team">{row.team}</span>
    <span className="nfl-game-side__who"><b><Link to={`/nfl/player/${row.playerId}`}>{row.playerName}</Link></b><small>{row.position} · {injuryLabel(row)}</small></span>
    <span className={`nfl-game-tag ${row.injuryStatus ? STATUS_CLASSES[row.injuryStatus] ?? '' : ''}`}>{tag?.label ?? 'Practice'}</span>
  </li>
}

function Injuries({ notes }: { notes: NflGameNotes }) {
  const rows = injuriesByTeam(notes.injuries, notes.awayTeam, notes.homeTeam).flatMap(([, teamRows]) => teamRows)
  return <Card title="Injury report" meta="QB RB WR TE">
    {rows.length ? <ul className="nfl-game-side__list">{rows.map(row => <InjuryRow key={`${row.team}-${row.playerName}-${row.position}`} row={row} />)}</ul> : <Empty text="Nobody on either team's report" />}
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

function FormRow({ form }: { form: NflTeamForm }) {
  const rest = restLabel(form)
  return <div className="nfl-game-side__form">
    <span className="nfl-game-side__who"><b>{form.team}</b>{rest && <small className={form.shortWeek ? 'is-short' : ''}>{rest}</small>}</span>
    {form.recent.length ? <ul>{form.recent.map(game => <li key={game.week}><small>Wk {game.week}</small>{formLabel(game)}</li>)}</ul> : <Empty text="No completed games this season" />}
  </div>
}

function StatsTable({ stats }: { stats: NflTeamStats }) {
  const games = gamesLabel(stats)
  if (!games) return <div className="nfl-game-side__stats"><b>{stats.team}</b><Empty text="No completed games this season" /></div>
  return <div className="nfl-game-side__stats">
    <b>{stats.team} <small>{games}{stats.games < SMALL_SAMPLE_GAMES && ' · small sample'}</small></b>
    <table><thead><tr><th scope="col" /><th scope="col">Off</th><th scope="col">Def</th></tr></thead>
      <tbody>{TEAM_STAT_ROWS.map(row => <tr key={row.label}><th scope="row">{row.label}</th>{[row.offense, row.defense].map(key => <td key={key}>{statValue(stats[key], row.kind)}<small>{rankLabel(stats[key].rank)}</small></td>)}</tr>)}</tbody>
    </table>
  </div>
}

/** Item 29/30 game notes as sidebar cards. Context only: never changes an edge or its rank. */
export function NflGameSidebar({ notes, isLoading, isError }: { notes: NflGameNotes | undefined, isLoading: boolean, isError: boolean }) {
  if (isLoading) return <aside className="nfl-game-side"><Card title="Game notes"><Empty text="Loading injuries, depth and team stats..." /></Card></aside>
  if (isError || !notes) return <aside className="nfl-game-side"><Card title="Game notes"><Empty text={isError ? 'Game notes are unavailable right now.' : 'No notes stored for this game.'} /></Card></aside>
  return <aside className="nfl-game-side" aria-label="Game notes">
    <Injuries notes={notes} />
    <DepthChanges notes={notes} />
    <Card title="Form and rest"><FormRow form={notes.awayForm} /><FormRow form={notes.homeForm} /></Card>
    <Card title="Team stats" meta="Season per game · rank of 32 · def = allowed"><StatsTable stats={notes.awayStats} /><StatsTable stats={notes.homeStats} /></Card>
    <p className="nfl-game-note is-inline">Context only. Injuries, depth and team stats never change an edge or its rank.</p>
  </aside>
}
