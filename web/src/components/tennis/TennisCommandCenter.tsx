import { Tooltip } from 'antd'
import { forwardRef, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import TennisSlateTable from '~/components/tennis/TennisSlateTable'
import { fmtEv, slateRows, tourTone } from '~/utils/tennisSlate'
import { fetchPlayerStats } from '~/api/tennis'
import type { BestPick, MatchPrediction, PlayerStats, PropLine } from '~/types/tennis'
import type { UnifiedTennisMatch } from '~/utils/unifiedTennis'
import { anglePicks, bestBetPicks, unifiedMatchToPrediction } from '~/utils/unifiedTennis'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtStartCT, fmtSurface, fmtTournament } from '~/utils/format'
import { getDisplayFlagLabel, getDisplayFlags } from '~/components/tennis/qualityFlags'
import './tennis-command-center.css'

interface Props {
  matches: UnifiedTennisMatch[]
  grouped: boolean
  selectedMatchKey: string | null
  onSelectMatch: (matchKey: string) => void
}

/** LOCK and STRONG are green; LEAN and unrated stay amber, as the old tags were orange. */
function ConfidenceTag({ value }: { value: string | null | undefined }) {
  const tone = value === 'LOCK' ? 'lock' : value === 'STRONG' ? 'strong' : 'lean'
  return <span className={`tennis-tier is-${tone}`}>{value ?? 'Review'}</span>
}

function BoardRow({ label, title, detail, cells, ev, confidence, isProp = false }: {
  label: string
  title: string
  detail: string
  cells: string[]
  ev: number | null | undefined
  confidence: string | null | undefined
  isProp?: boolean
}) {
  return (
    <div className={`tennis-panel-row${isProp ? ' is-prop' : ''}`}>
      <span className="tennis-panel-label">{label}</span>
      <strong>{title}</strong>
      {detail && <small>{detail}</small>}
      <div className="tennis-panel-row__cells">
        {cells.map((cell, index) => <span key={index}>{cell}</span>)}
        <span className="tennis-panel-ev">{fmtEv(ev)}</span>
        <ConfidenceTag value={confidence} />
      </div>
    </div>
  )
}

function PickRow({ pick, label }: { pick: BestPick; label: string }) {
  return (
    <BoardRow
      label={label}
      title={pick.pick}
      detail={pick.reasoning}
      cells={[fmtAmerican(pick.oddsAmerican), `Model ${fmtPct(pick.modelProb)}`, `Mkt ${fmtPct(pick.marketProb)}`]}
      ev={pick.evPct}
      confidence={pick.confidence}
    />
  )
}

function PropRow({ prop }: { prop: PropLine }) {
  const line = prop.line == null ? '—' : Number(prop.line).toFixed(1)
  return (
    <BoardRow
      label="Player prop"
      title={`${prop.playerName} · ${prop.statType}`}
      detail={`${prop.recommendation?.toUpperCase() ?? 'Review'} ${line}`}
      cells={[`Line ${line}`, `Hit ${fmtPct(prop.hitProbability)}`, `${prop.matchesCount ?? '—'} match sample`]}
      ev={prop.evPct}
      confidence={prop.confidence}
      isProp
    />
  )
}

type Measure = [label: string, first: number | null | undefined, second: number | null | undefined]

function measureValue(value: number | null | undefined): string {
  return value == null ? '—' : fmtPct(value)
}

function usePlayerStats(match: MatchPrediction): [PlayerStats | null, PlayerStats | null] {
  const [stats, setStats] = useState<[PlayerStats | null, PlayerStats | null]>([null, null])
  useEffect(() => {
    let active = true
    Promise.all([
      fetchPlayerStats(match.p1Name, match.tour, match.surface),
      fetchPlayerStats(match.p2Name, match.tour, match.surface),
    ])
      .then((result) => { if (active) setStats(result) })
      .catch(() => { if (active) setStats([null, null]) })
    return () => { active = false }
  }, [match])
  return stats
}

function surfaceElo(match: MatchPrediction, p1: PlayerStats | null, p2: PlayerStats | null): [number | null | undefined, number | null | undefined] {
  if (match.surface === 'Hard') return [p1?.eloHard, p2?.eloHard]
  if (match.surface === 'Clay') return [p1?.eloClay, p2?.eloClay]
  if (match.surface === 'Grass') return [p1?.eloGrass, p2?.eloGrass]
  return [p1?.elo, p2?.elo]
}

function InlineAnalysis({ match }: { match: MatchPrediction }) {
  const [p1, p2] = usePlayerStats(match)
  const models = [['ELO', match.p1EloProb], ['ML', match.p1MlProb], ['Market', match.p1MarketProb]]
    .filter((item): item is [string, number] => item[1] != null)
  // The rolling-stat names mislead: acesPerGame and dfPerGame are per serve point and
  // breakPct is break points converted (app/ingest/player_stats.py), so label them so.
  const measures: Measure[] = [
    ['Serve pts won', p1?.svcPtsWon, p2?.svcPtsWon], ['Return pts won', p1?.retPtsWon, p2?.retPtsWon],
    ['Ace rate', p1?.acesPerGame, p2?.acesPerGame], ['DF rate', p1?.dfPerGame, p2?.dfPerGame],
    ['Hold rate', p1?.holdPct, p2?.holdPct], ['BP converted', p1?.breakPct, p2?.breakPct], ['Win rate', p1?.winRate, p2?.winRate],
  ]
  const elo = surfaceElo(match, p1, p2)
  const round = (value: number | null | undefined) => (value == null ? '—' : Math.round(value))
  return (
    <section className="tennis-panel-section">
      <h3 className="tennis-panel-heading">Match intelligence</h3>
      <div className="tennis-panel-facts">
        <div><span className="tennis-panel-label">Head-to-head</span><strong>{match.h2hP1Wins} - {match.h2hP2Wins}</strong></div>
        <div><span className="tennis-panel-label">{match.surface ?? 'Overall'} ELO</span><strong>{round(elo[0])} - {round(elo[1])}</strong></div>
      </div>
      <span className="tennis-panel-label">Model breakdown</span>
      {models.map(([label, value]) => <div key={label} className="tennis-panel-model">{label}<span>{fmtPct(value)} / {fmtPct(1 - value)}</span></div>)}
      <span className="tennis-panel-label">Serve and return · last 52 weeks</span>
      <div className="tennis-panel-measures">
        {measures.map(([label, first, second]) => (
          <div key={label}><span>{measureValue(first)}</span><small>{label}</small><span>{measureValue(second)}</span></div>
        ))}
      </div>
    </section>
  )
}

function PlayerName({ id, name }: { id: number | null | undefined; name: string }) {
  if (id == null) return <strong>{name}</strong>
  return <strong><Link className="tennis-name-link" to={`/tennis/player/${id}`}>{name}</Link></strong>
}

function MatchupHeader({ match, prediction }: { match: UnifiedTennisMatch; prediction: MatchPrediction | null }) {
  const qualityFlags = prediction ? getDisplayFlags(prediction.qualityFlags).slice(0, 3) : []
  const surface = fmtSurface(prediction?.surface ?? null)
  const tone = tourTone(prediction?.tour, prediction?.tourLabel)
  const start = fmtStartCT(prediction?.startUtc ?? match.props[0]?.startTime)
  return (
    <header className="tennis-panel-matchup">
      <div className="tennis-panel-label">{fmtTournament(prediction?.tournament ?? null)} · {prediction?.round ?? 'Match'} · {start ?? 'Time TBA'}</div>
      <div className="tennis-panel-player">
        <PlayerName id={prediction?.p1Id} name={prediction?.p1Name ?? match.props[0]?.playerName ?? 'Player unavailable'} />
        <span>{prediction ? `${fmtAmerican(prediction.p1OddsAmerican)} · ${fmtPct(prediction.p1WinProb)}` : 'Player props'}</span>
      </div>
      <div className="tennis-panel-player">
        <PlayerName id={prediction?.p2Id} name={prediction?.p2Name ?? 'Market context unavailable'} />
        <span>{prediction ? `${fmtAmerican(prediction.p2OddsAmerican)} · ${fmtPct(prediction.p2WinProb)}` : surface}</span>
      </div>
      <div className="tennis-panel-tags">
        {surface && <span className="tennis-panel-tag">{surface}</span>}
        {prediction?.tourLabel && <span className={`tennis-tour-tag${tone ? ` is-${tone}` : ''}`}>{prediction.tourLabel}</span>}
        {qualityFlags.map((flag) => (
          <Tooltip key={flag} title={getDisplayFlagLabel(prediction!, flag)}><span className="tennis-panel-tag">{flag.replaceAll('_', ' ')}</span></Tooltip>
        ))}
      </div>
      {prediction && <Link className="tennis-panel-open" to={`/tennis/match/${prediction.matchId}`}>Open match analysis →</Link>}
    </header>
  )
}

function FeaturedOpportunity({ pick, prop }: { pick: BestPick | undefined; prop: PropLine | undefined }) {
  if (!pick && !prop) return null
  const stats: Array<[string, string]> = pick
    ? [['Model', fmtPct(pick.modelProb)], ['Market', fmtPct(pick.marketProb)]]
    : [['Hit probability', fmtPct(prop!.hitProbability)], ['Sample', `${prop!.matchesCount ?? '—'} matches`]]
  return (
    <section className="tennis-panel-featured">
      <span className="tennis-panel-label">Best opportunity</span>
      <strong>{pick ? pick.pick : `${prop!.playerName} · ${prop!.statType}`}</strong>
      <small>{pick ? pick.reasoning : `${prop!.recommendation?.toUpperCase() ?? 'Review'} ${prop!.line ?? '—'} player prop`}</small>
      <div className="tennis-panel-featured__stats">
        {stats.map(([label, value]) => <div key={label}><span className="tennis-panel-label">{label}</span><b>{value}</b></div>)}
        <div><span className="tennis-panel-label">Expected value</span><b className="tennis-panel-ev">{fmtEv(pick ? pick.evPct : prop!.evPct)}</b></div>
      </div>
      <ConfidenceTag value={pick ? pick.confidence : prop!.confidence} />
    </section>
  )
}

const SelectedMatchWorkspace = forwardRef<HTMLElement, { match: UnifiedTennisMatch }>(function SelectedMatchWorkspace({ match }, ref) {
  const prediction = unifiedMatchToPrediction(match)
  const bestPicks = bestBetPicks(match)
  const angles = anglePicks(match)
  const primaryProp = [...match.props].sort((left, right) => (right.evPct ?? Number.NEGATIVE_INFINITY) - (left.evPct ?? Number.NEGATIVE_INFINITY))[0]
  const primaryPick = bestPicks[0] ?? angles[0]
  const signals = bestPicks.length + angles.length + match.props.length
  return (
    <section ref={ref} className="tennis-command-workspace" aria-label="Selected match">
      <MatchupHeader match={match} prediction={prediction} />
      <FeaturedOpportunity pick={primaryPick} prop={primaryPick ? undefined : primaryProp} />
      {prediction && <InlineAnalysis match={prediction} />}
      <section className="tennis-panel-section">
        <h3 className="tennis-panel-heading">Decision board <span>{signals} signals</span></h3>
        {bestPicks.map((pick, index) => <PickRow key={`${pick.pick}-${index}`} pick={pick} label="Best bet" />)}
        {angles.map((pick, index) => <PickRow key={`${pick.pick}-${index}`} pick={pick} label="Angle" />)}
        {match.props.map((prop) => <PropRow key={prop.id} prop={prop} />)}
        {signals === 0 && <div className="tennis-panel-empty">No scored opportunities are available for this match.</div>}
      </section>
    </section>
  )
})

// Matches the tennis-slate.css breakpoint where the panel stacks under the table.
const STACKED_QUERY = '(max-width: 1100px)'

export default function TennisCommandCenter({ matches, grouped, selectedMatchKey, onSelectMatch }: Props) {
  const selectedMatch = matches.find((match) => match.key === selectedMatchKey)
    ?? matches.find((match) => bestBetPicks(match).length > 0 || anglePicks(match).length > 0)
    ?? matches[0]
  const panelRef = useRef<HTMLElement>(null)
  if (!selectedMatch) return null
  function selectRow(key: string) {
    onSelectMatch(key)
    // Stacked, the panel sits below the whole table, so bring it to the reader.
    if (window.matchMedia(STACKED_QUERY).matches) {
      requestAnimationFrame(() => panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    }
  }
  return (
    <div className="tennis-command-layout">
      <TennisSlateTable rows={slateRows(matches)} grouped={grouped} selectedKey={selectedMatch.key} onSelect={selectRow} />
      <SelectedMatchWorkspace ref={panelRef} match={selectedMatch} />
    </div>
  )
}
