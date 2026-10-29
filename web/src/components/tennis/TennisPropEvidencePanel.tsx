import { Tag } from 'antd'
import { Link } from 'react-router-dom'
import type { CSSProperties, Ref } from 'react'
import { useMatchRecentForm } from '~/hooks/useMatchRecentForm'
import type { PlayerFormStats, PlayerRecentForm } from '~/types/tennis'
import type { TennisBoardLine } from '~/utils/tennisPropBoard'
import { lineNumber, marketLabel, signalSummary, sourceLabel } from '~/utils/tennisPropBoard'
import { propCard, recentStatBars } from '~/utils/tennisPropCards'
import { propMatchPath } from '~/utils/tennisMatchView'

function percent(value: number | null | undefined): string {
  return value == null ? '--' : `${(value * 100).toFixed(1)}%`
}

function flagLabel(flag: string): string {
  return flag.replaceAll('_', ' ')
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(`${value}T12:00:00`))
}

function exactPropResult(statType: string, match: PlayerRecentForm['matches'][number]): string | null {
  const market = statType.toLowerCase()
  if (market.includes('ace')) return match.aces == null ? null : `Aces: ${match.aces}`
  if (market.includes('double') || market === 'dfs') return match.doubleFaults == null ? null : `Double faults: ${match.doubleFaults}`
  if (market.includes('break')) {
    if (match.breakPointsConverted == null || match.breakChancesCreated == null) return null
    const rate = match.breakChancesCreated > 0 ? ` (${((match.breakPointsConverted / match.breakChancesCreated) * 100).toFixed(0)}%)` : ''
    return `Breaks: ${match.breakPointsConverted}/${match.breakChancesCreated}${rate}`
  }
  return null
}

function FormHistory({ player, statType }: { player: PlayerRecentForm, statType: string }) {
  const wins = player.matches.filter(match => match.result === 'W').length
  return <article className="tennis-prop-form__history"><h3>{player.playerName}<small>{player.matches.length ? `${wins}-${player.matches.length - wins} · last ${player.matches.length}` : 'No completed history'}</small></h3>{player.matches.map(match => <div key={`${match.matchDate}-${match.opponentName}`}><strong className={match.result === 'W' ? 'is-win' : 'is-loss'}>{match.result}</strong><span>{dateLabel(match.matchDate)} vs {match.opponentName}</span><em>{[match.score ?? 'Score unavailable', exactPropResult(statType, match)].filter(Boolean).join(' · ')}</em></div>)}</article>
}

function FormStats({ players }: { players: PlayerRecentForm[] }) {
  const left = players[0]
  const right = players[1]
  // acesPerGame and dfPerGame are per serve point and breakPct is break points
  // converted (app/ingest/player_stats.py), whatever the field names say.
  const measures: Array<[keyof PlayerFormStats, string]> = [
    ['svcPtsWon', 'Serve pts won'], ['retPtsWon', 'Return pts won'], ['acesPerGame', 'Ace rate'], ['dfPerGame', 'DF rate'], ['holdPct', 'Hold rate'], ['breakPct', 'BP converted'], ['winRate', 'Win rate'],
  ]
  if (!left || !right) return <section className="tennis-prop-form"><span>Serve &amp; return · last 52 weeks</span><p>Form comparison unavailable.</p></section>
  return <section className="tennis-prop-form"><span>Serve &amp; return · last 52 weeks</span><div className="tennis-prop-form__names"><strong>{left.playerName}</strong><strong>{right.playerName}</strong></div><div className="tennis-prop-form__stats">{measures.map(([key, label]) => <div key={key}><strong>{percent(left.last52W?.[key])}</strong><span>{label}</span><strong>{percent(right.last52W?.[key])}</strong></div>)}</div></section>
}

function linePlayer(row: TennisBoardLine, players: PlayerRecentForm[]): PlayerRecentForm | null {
  if (row.playerId != null) return players.find(player => player.playerId === row.playerId) ?? null
  const name = (row.playerName ?? '').trim().toLowerCase()
  return players.find(player => player.playerName.trim().toLowerCase() === name) ?? null
}

/** The selected player's recent box-score values against today's line; no rate or count on purpose. */
function RecentBars({ row, players }: { row: TennisBoardLine, players: PlayerRecentForm[] }) {
  const line = lineNumber(row)
  const player = linePlayer(row, players)
  const bars = player && line != null ? recentStatBars(player.matches, row.statType, line) : null
  if (!player || line == null || !bars?.some(bar => bar.value != null)) return null
  const scale = Math.max(line, ...bars.map(bar => bar.value ?? 0)) * 1.15 || 1
  const columns: CSSProperties = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` }
  const summary = bars.map(bar => bar.value ?? 'no data').join(', ')
  return <section className="tennis-prop-form tennis-prop-bars">
    <span>{marketLabel(row.statType)} · last {bars.length}</span>
    <div className="tennis-prop-bars__values" style={columns} aria-hidden="true">{bars.map(bar => <em key={bar.matchDate}>{bar.value ?? '--'}</em>)}</div>
    <div className="tennis-prop-bars__chart" role="img" aria-label={`Oldest to newest: ${summary}, against the ${line.toFixed(1)} line`} style={{ ...columns, '--line': `${(line / scale) * 100}%` } as CSSProperties}>
      {bars.map(bar => <i key={bar.matchDate} className={bar.vsLine ? `is-${bar.vsLine}` : 'is-missing'} style={{ '--h': `${((bar.value ?? 0) / scale) * 100}%` } as CSSProperties} />)}
    </div>
    <div className="tennis-prop-bars__dates" style={columns} aria-hidden="true">{bars.map(bar => <small key={bar.matchDate} title={`vs ${bar.opponentName}`}>{dateLabel(bar.matchDate)}</small>)}</div>
    <small className="tennis-prop-bars__line">Dashed line: today's {line.toFixed(1)} line</small>
  </section>
}

function LineSummary({ row }: { row: TennisBoardLine }) {
  const card = propCard(row)
  const side = card.pickTone === 'positive' ? '' : ` is-${card.pickTone}`
  return <>
    <p>{row.matchup ?? 'Match unavailable'}</p>
    <p>{card.startText}</p>
    <div className="tennis-prop-evidence__summary">
      <span className={`tennis-prop-evidence__pick${side}`}>{card.pickLabel}</span>
      <b>{card.valueText}</b>
      {card.evText !== '--' && <span className={`tennis-prop-evidence__ev${card.evTone ? ` is-${card.evTone}` : ''}`}>{card.evText} EV</span>}
    </div>
  </>
}

function ContextFacts({ row }: { row: TennisBoardLine }) {
  const opponent = row.opponentStatAvg == null ? 'Unavailable' : `${row.opponentStatAvg.toFixed(1)} avg${row.opponentMatchesCount ? ` · ${row.opponentMatchesCount} matches` : ''}`
  return <div className="tennis-prop-evidence__grid">
    <div><span>Event</span><strong>{[row.tournament, row.surface].filter(Boolean).join(' · ') || 'Unavailable'}</strong></div>
    <div><span>Opponent allows</span><strong>{opponent}</strong></div>
    <div><span>Projection basis</span><strong>{row.projectionSource?.replaceAll('_', ' ') ?? 'Rolling player stats'}</strong></div>
  </div>
}

export default function TennisPropEvidencePanel({ row, ref, showMatchLink = true }: { row: TennisBoardLine, ref?: Ref<HTMLElement>, showMatchLink?: boolean }) {
  const flags = row.dataQualityFlags ?? []
  const inputs = Object.entries(row.projectionInputs ?? {})
  const recentForm = useMatchRecentForm(row.matchId)
  return <aside ref={ref} className="tennis-prop-evidence" aria-label={`Evidence for ${row.playerName ?? 'selected prop'}`}>
    <header>
      <h2>{row.playerName ?? 'Unknown player'}</h2>
      <p>{marketLabel(row.statType)} · {sourceLabel(row.source)}</p>
      <LineSummary row={row} />
      {showMatchLink && propMatchPath(row) && <Link to={propMatchPath(row)!} className="tennis-prop-text-action">Open match picks &amp; props</Link>}
    </header>
    <section className="tennis-prop-evidence__reason"><span>Why this signal</span><p>{signalSummary(row)}</p></section>
    <ContextFacts row={row} />
    {inputs.length > 0 && <section className="tennis-prop-evidence__inputs"><span>Projection inputs</span><div>{inputs.map(([key, value]) => <Tag key={key}>{key.replaceAll('_', ' ')}: {typeof value === 'number' ? value.toFixed(2) : value}</Tag>)}</div></section>}
    {recentForm.isLoading && <section className="tennis-prop-form"><span>Player form</span><p>Loading last five matches...</p></section>}
    {recentForm.isError && <section className="tennis-prop-form"><span>Player form</span><p>Recent form is unavailable.</p></section>}
    {recentForm.data && <><RecentBars row={row} players={recentForm.data.players} /><FormStats players={recentForm.data.players} /><section className="tennis-prop-form tennis-prop-form--history"><span>Last 5 completed matches</span><div className="tennis-prop-form__histories">{recentForm.data.players.map(player => <FormHistory key={player.playerId} player={player} statType={row.statType} />)}</div></section></>}
    {flags.length > 0 && <section className="tennis-prop-evidence__inputs"><span>Quality notes</span><div>{flags.map(flag => <Tag key={flag}>{flagLabel(flag)}</Tag>)}</div></section>}
  </aside>
}
