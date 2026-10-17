import { Tooltip } from 'antd'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fmtEv, tourTone } from '~/utils/tennisSlate'
import { fetchPlayerStats } from '~/api/tennis'
import type { BestPick, MatchPrediction, PlayerStats, PropLine } from '~/types/tennis'
import type { UnifiedTennisMatch } from '~/utils/unifiedTennis'
import { anglePicks, bestBetPicks, unifiedMatchToPrediction } from '~/utils/unifiedTennis'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtStartCT, fmtSurface, fmtTournament } from '~/utils/format'
import { getDisplayFlagLabel, getDisplayFlags } from '~/components/tennis/qualityFlags'
import './tennis-match-detail.css'

const MISSING = '--'
const BEST_BET = 'Best bet'

/** Gray: no tennis tier has passed the 32b tier rule yet. */
function ConfidenceTag({ value }: { value: string | null | undefined }) {
  return <span className="tennis-tier is-neutral">{value ?? 'Review'}</span>
}

/** Green only for a priced best bet's positive EV, the table and digest rule. */
function evClass(item: PickItem): string {
  const positive = item.kind === BEST_BET && item.ev != null && item.ev > 0
  return `tennis-detail__ev${positive ? ' is-positive' : ''}`
}

interface PickItem {
  key: string
  kind: string
  title: string
  detail: string
  cells: string[]
  ev: number | null | undefined
  confidence: string | null | undefined
}

function pickItem(pick: BestPick, kind: string, index: number): PickItem {
  return {
    key: `${kind}-${pick.pick}-${index}`,
    kind,
    title: pick.pick,
    detail: pick.reasoning,
    cells: [fmtAmerican(pick.oddsAmerican), `Model ${fmtPct(pick.modelProb)}`, `Mkt ${fmtPct(pick.marketProb)}`],
    ev: pick.evPct,
    confidence: pick.confidence,
  }
}

function propItem(prop: PropLine): PickItem {
  const line = prop.line == null ? MISSING : Number(prop.line).toFixed(1)
  return {
    key: `prop-${prop.id}`,
    kind: 'Player prop',
    title: `${prop.playerName} · ${prop.statType}`,
    detail: `${prop.recommendation?.toUpperCase() ?? 'Review'} ${line}`,
    cells: [`Line ${line}`, `Hit ${fmtPct(prop.hitProbability)}`, `${prop.matchesCount ?? MISSING} match sample`],
    ev: prop.evPct,
    confidence: prop.confidence,
  }
}

/**
 * Best bets, then angles, then props: the old decision board's order. With no pick, the
 * highest-EV prop leads, as the old "best opportunity" box showed it.
 */
function pickItems(match: UnifiedTennisMatch): PickItem[] {
  const picks = [
    ...bestBetPicks(match).map((pick, index) => pickItem(pick, BEST_BET, index)),
    ...anglePicks(match).map((pick, index) => pickItem(pick, 'Angle', index)),
  ]
  const props = match.props.map(propItem)
  if (picks.length > 0 || props.length < 2) return [...picks, ...props]
  const top = props.reduce((best, item) => ((item.ev ?? Number.NEGATIVE_INFINITY) > (best.ev ?? Number.NEGATIVE_INFINITY) ? item : best))
  return [top, ...props.filter((item) => item !== top)]
}

function Picks({ items }: { items: PickItem[] }) {
  return (
    <section className="tennis-detail__section">
      <h3 className="tennis-detail__label">Picks <span>{items.length}</span></h3>
      {items.length === 0 && <p className="tennis-detail__empty">No scored opportunities for this match.</p>}
      {items.map((item) => (
        <div key={item.key} className="tennis-detail__pick">
          <span className="tennis-detail__kind">{item.kind}</span>
          <strong>{item.title}</strong>
          {item.detail && <small>{item.detail}</small>}
          <div className="tennis-detail__cells">
            {item.cells.map((cell, index) => <span key={index}>{cell}</span>)}
            <span className={evClass(item)}>{fmtEv(item.ev)}</span>
            <ConfidenceTag value={item.confidence} />
          </div>
        </div>
      ))}
    </section>
  )
}

type Measure = [label: string, first: number | null | undefined, second: number | null | undefined]

function measureValue(value: number | null | undefined): string {
  return value == null ? MISSING : fmtPct(value)
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

function surname(name: string): string {
  return name.trim().split(/\s+/).pop() ?? name
}

function MatchAndServe({ match }: { match: MatchPrediction }) {
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
  const round = (value: number | null | undefined) => (value == null ? MISSING : Math.round(value))
  const facts: Array<[string, string]> = [
    ['Head-to-head', `${match.h2hP1Wins} - ${match.h2hP2Wins}`],
    [`${match.surface ?? 'Overall'} ELO`, `${round(elo[0])} - ${round(elo[1])}`],
    ...models.map(([label, value]): [string, string] => [label, `${fmtPct(value)} / ${fmtPct(1 - value)}`]),
  ]
  return (
    <>
      <section className="tennis-detail__section">
        <h3 className="tennis-detail__label">Match</h3>
        {facts.map(([label, value]) => (
          <div key={label} className="tennis-detail__fact"><span>{label}</span><b>{value}</b></div>
        ))}
      </section>
      <section className="tennis-detail__section">
        <div className="tennis-detail__measure is-head">
          <h3 className="tennis-detail__label">Serve and return · 52 wk</h3>
          <span title={match.p1Name}>{surname(match.p1Name)}</span>
          <span title={match.p2Name}>{surname(match.p2Name)}</span>
        </div>
        {measures.map(([label, first, second]) => (
          <div key={label} className="tennis-detail__measure">
            <small>{label}</small><span>{measureValue(first)}</span><span>{measureValue(second)}</span>
          </div>
        ))}
      </section>
    </>
  )
}

function PlayerLink({ id, name }: { id: number | null | undefined; name: string }) {
  if (id == null) return <strong>{name}</strong>
  return <strong><Link className="tennis-name-link" to={`/tennis/player/${id}`}>{name}</Link></strong>
}

function Context({ match, prediction, showFlags }: { match: UnifiedTennisMatch; prediction: MatchPrediction | null; showFlags: boolean }) {
  const qualityFlags = prediction && showFlags ? getDisplayFlags(prediction.qualityFlags).slice(0, 3) : []
  const surface = fmtSurface(prediction?.surface ?? null)
  const tone = tourTone(prediction?.tour, prediction?.tourLabel)
  const start = fmtStartCT(prediction?.startUtc ?? match.props[0]?.startTime) || 'Time TBA'
  const where = prediction ? `${fmtTournament(prediction.tournament)} · ${prediction.round ?? 'Match'} · ${start}` : `Player props · ${start}`
  return (
    <header className="tennis-detail__context">
      <span className="tennis-detail__where">{where}</span>
      {(surface || prediction?.tourLabel || qualityFlags.length > 0) && <span className="tennis-detail__tags">
        {surface && <span className="tennis-detail__tag">{surface}</span>}
        {prediction?.tourLabel && <span className={`tennis-tour-tag${tone ? ` is-${tone}` : ''}`}>{prediction.tourLabel}</span>}
        {qualityFlags.map((flag) => (
          <Tooltip key={flag} title={getDisplayFlagLabel(prediction!, flag)}><span className="tennis-detail__tag">{flag.replaceAll('_', ' ')}</span></Tooltip>
        ))}
      </span>}
      {prediction && <span className="tennis-detail__players">
        <span><PlayerLink id={prediction.p1Id} name={prediction.p1Name} /> {fmtAmerican(prediction.p1OddsAmerican)} · {fmtPct(prediction.p1WinProb)}</span>
        <span><PlayerLink id={prediction.p2Id} name={prediction.p2Name} /> {fmtAmerican(prediction.p2OddsAmerican)} · {fmtPct(prediction.p2WinProb)}</span>
      </span>}
      {prediction && <Link className="tennis-detail__open" to={`/tennis/match/${prediction.matchId}`}>Open match analysis →</Link>}
    </header>
  )
}

/** One match's detail under its slate row: a context line, then picks, match facts, and serve and return. */
export default function TennisMatchDetail({ match, showFlags }: { match: UnifiedTennisMatch; showFlags: boolean }) {
  const prediction = unifiedMatchToPrediction(match)
  return (
    <>
      <Context match={match} prediction={prediction} showFlags={showFlags} />
      <div className={`tennis-detail__grid${prediction ? '' : ' is-props-only'}`}>
        <Picks items={pickItems(match)} />
        {prediction && <MatchAndServe match={prediction} />}
      </div>
    </>
  )
}
