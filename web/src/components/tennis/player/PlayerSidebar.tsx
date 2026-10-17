import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import ErrorState from '~/components/shared/ErrorState'
import { usePlayerProps } from '~/hooks/useTennisPlayer'
import type { PastProp, PlayerDetail, PlayerMatches, WinLoss } from '~/types/tennis'
import { fmtDateCT, fmtTimeCT } from '~/utils/format'
import { marketTitle } from '~/utils/tennisPropBoard'
import { dateWithYear, recordText, shortDate } from '~/utils/tennisPlayer'

const PROPS_SHOWN = 12

function Card({ title, children }: { title: string, children: ReactNode }) {
  return (
    <div className="tennis-match-card tennis-match-aside">
      <h3>{title}</h3>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string, value: string }) {
  return <div className="tennis-match-kv"><span>{label}</span><span>{value}</span></div>
}

function RecordCard({ query }: { query: UseQueryResult<PlayerMatches> }) {
  if (query.isLoading) return <Card title="Record · 52 weeks"><p className="tennis-match-aside__empty">Loading...</p></Card>
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const r = query.data.record
  if (r.all.wins + r.all.losses === 0) {
    return <Card title="Record · 52 weeks"><p className="tennis-match-aside__empty">No completed matches in the last 52 weeks.</p></Card>
  }
  const rows: [string, WinLoss][] = [
    ['All', r.all], ['Hard', r.hard], ['Clay', r.clay], ['Grass', r.grass],
    ['vs top 20', r.vsTop20], ['Deciding sets', r.decidingSets], ['Tie-break sets', r.tieBreaks],
  ]
  return (
    <Card title="Record · 52 weeks">
      {rows.map(([label, split]) => <Row key={label} label={label} value={recordText(split)} />)}
      <p className="tennis-match-aside__note">
        Since {dateWithYear(r.windowStart)}. Deciding sets and tie-break sets count finished scores only, so a
        retirement or a match tie-break decider counts in the record but not in those two rows.
      </p>
    </Card>
  )
}

const OUTCOME_TEXT: Record<PastProp['outcome'], string> = {
  hit: 'hit', miss: 'miss', push: 'push', pass: 'no pick', void: 'void', awaiting: 'pending', ungradable: 'no source',
}

function PickCell({ prop }: { prop: PastProp }) {
  const side = prop.recommendation ? prop.recommendation.charAt(0) + prop.recommendation.slice(1).toLowerCase() : '—'
  const tone = prop.outcome === 'hit' ? 'is-hit' : prop.outcome === 'miss' ? 'is-miss' : 'is-faint'
  return <td className="l pick">{side} · <span className={`tennis-player-outcome ${tone}`}>{OUTCOME_TEXT[prop.outcome]}</span></td>
}

function PropsCard({ playerId, name }: { playerId: number, name: string }) {
  const query = usePlayerProps(playerId)
  const title = 'Past props · settled'
  if (query.isLoading) return <Card title={title}><p className="tennis-match-aside__empty">Loading...</p></Card>
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  const { rows, summary, projectionVersion } = query.data
  if (rows.length === 0) {
    return (
      <Card title={title}>
        <p className="tennis-match-aside__empty">
          No settled PrizePicks lines for {name} yet. Snapshots start 2026-09-25 and are kept for {projectionVersion}.
        </p>
      </Card>
    )
  }
  return (
    <Card title={title}>
      <div className="tennis-player-props-scroll">
        <table className="tennis-player-table tennis-player-props">
          <thead><tr><th>Date</th><th className="l">Stat</th><th>Line</th><th>Actual</th><th className="l pick">Pick</th></tr></thead>
          <tbody>
            {rows.slice(0, PROPS_SHOWN).map((prop, i) => (
              <tr key={`${prop.snapshotDate}-${prop.stat}-${prop.oddsType}-${prop.line}-${i}`}>
                <td>{shortDate(prop.snapshotDate)}</td>
                <td className="l stat">{marketTitle(prop.stat)}{prop.oddsType !== 'standard' && <span className="tennis-player-faint"> {prop.oddsType}</span>}</td>
                <td>{prop.line}</td>
                <td className={prop.outcome === 'hit' ? 'tennis-player-outcome is-hit' : ''}>{prop.actual ?? '—'}</td>
                <PickCell prop={prop} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Row label={`Model picks on ${name}`} value={recordText({ wins: summary.hits, losses: summary.misses })} />
      <p className="tennis-match-aside__note">
        {rows.length > PROPS_SHOWN ? `Newest ${PROPS_SHOWN} of ${rows.length} lines. ` : ''}
        The pick is the frozen pre-match recommendation ({projectionVersion}); the record counts standard lines only.
        A handful of picks is anecdote, not evidence: the model page grades the full sample.
      </p>
    </Card>
  )
}

function IdentityCard({ player }: { player: PlayerDetail }) {
  const computed = player.statsComputedAt ? `${fmtDateCT(player.statsComputedAt)} ${fmtTimeCT(player.statsComputedAt)}` : '—'
  return (
    <Card title="Identity">
      <Row label="Aliases" value={player.aliases.length ? player.aliases.join(', ') : 'None'} />
      <Row label="ELO as of" value={player.elo.asOf ? shortDate(player.elo.asOf) : '—'} />
      <Row label="Stats computed" value={computed} />
    </Card>
  )
}

export default function PlayerSidebar({ player, matches }: { player: PlayerDetail, matches: UseQueryResult<PlayerMatches> }) {
  return (
    <aside className="tennis-player-side">
      <RecordCard query={matches} />
      <PropsCard playerId={player.playerId} name={player.name} />
      <IdentityCard player={player} />
    </aside>
  )
}
