import { Link } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import type { PlayerMatches } from '~/types/tennis'
import type { UseQueryResult } from '@tanstack/react-query'
import { ratio, shortDate } from '~/utils/tennisPlayer'

const dash = (value: number | null) => (value == null ? '—' : value)

export default function PlayerMatchLog({ query }: { query: UseQueryResult<PlayerMatches> }) {
  const heading = <h2 className="tennis-match-section">Match log</h2>
  if (query.isLoading) return <>{heading}<div className="tennis-match-empty">Loading matches...</div></>
  if (query.isError || !query.data) return <>{heading}<ErrorState error={query.error} onRetry={() => void query.refetch()} /></>

  const { log } = query.data
  if (log.length === 0) return <>{heading}<div className="tennis-match-empty">No completed matches on record yet.</div></>

  return (
    <>
      {heading}
      <div className="tennis-match-card tennis-player-log">
        <table className="tennis-player-table">
          <thead>
            <tr>
              <th>Date</th><th className="l">Event</th><th className="l">Opponent</th><th className="l">Score</th>
              <th>Aces</th><th>DF</th><th>BP saved</th><th>BP won</th>
            </tr>
          </thead>
          <tbody>
            {log.map((m) => (
              <tr key={m.matchId}>
                <td>{shortDate(m.matchDate)}</td>
                <td className="l">
                  {[m.tournament, m.round].filter(Boolean).join(' ')}
                  {m.surface && <span className="tennis-player-faint"> {m.surface.toLowerCase()}</span>}
                </td>
                <td className="l">
                  <span className={`tennis-player-res${m.result === 'L' ? ' is-loss' : ''}`}>{m.result}</span>
                  <Link to={`/tennis/player/${m.opponentId}`}>{m.opponentName}</Link>
                  {m.opponentRank != null && <span className="tennis-player-faint num"> #{m.opponentRank}</span>}
                </td>
                <td className="l num"><Link to={`/tennis/match/${m.matchId}`}>{m.score || '—'}</Link></td>
                <td>{dash(m.aces)}</td>
                <td>{dash(m.doubleFaults)}</td>
                <td>{ratio(m.bpSaved, m.bpFaced)}</td>
                <td>{ratio(m.bpWon, m.bpCreated)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="tennis-player-note">
        Last {log.length} completed matches. TennisAbstract box scores take precedence, with TennisMyLife filling
        gaps. Rows join by opponent and score; a dash means no matching count is available.
      </p>
    </>
  )
}
