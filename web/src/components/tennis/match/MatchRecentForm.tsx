import type { MatchDetail, PlayerRecentForm } from '~/types/tennis'
import { useMatchRecentForm } from '~/hooks/useMatchRecentForm'
import { fmtBreakPoints, fmtMatchDate } from '~/utils/tennisMatch'

function num(value: number | null): string {
  return value == null ? '—' : String(value)
}

/** Each set stays whole, so a long score wraps between sets, never inside "6-3". */
function Score({ score }: { score: string }) {
  return <>{score.split(' ').map((set, i) => <span key={i} className="tennis-match-set">{i > 0 ? ' ' : ''}{set}</span>)}</>
}

function FormCard({ name, form }: { name: string; form: PlayerRecentForm | undefined }) {
  const matches = form?.matches ?? []
  return (
    <div className="tennis-match-card tennis-match-form">
      <h3>{name}</h3>
      {matches.length === 0 ? (
        <p className="tennis-match-form__empty">No completed matches on record before this one.</p>
      ) : (
        <>
          <div className="tennis-match-wl" aria-label={`Last ${matches.length}: ${matches.map((m) => m.result).join(' ')}`}>
            {matches.map((m, i) => <b key={i} className={m.result === 'W' ? 'is-win' : ''}>{m.result}</b>)}
          </div>
          <table className="tennis-match-table">
            <thead>
              <tr><th>Opponent</th><th>Score</th><th>Aces</th><th>DF</th><th>BP won</th></tr>
            </thead>
            <tbody>
              {matches.map((m, i) => (
                <tr key={i}>
                  <td>
                    <span className={`tennis-match-res${m.result === 'W' ? '' : ' is-loss'}`}>{m.result}</span>
                    {m.opponentName}
                    <small>{fmtMatchDate(m.matchDate)}</small>
                  </td>
                  <td>{m.score ? <Score score={m.score} /> : '—'}</td>
                  <td>{num(m.aces)}</td>
                  <td>{num(m.doubleFaults)}</td>
                  <td>{fmtBreakPoints(m.breakPointsConverted, m.breakChancesCreated)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}

export default function MatchRecentForm({ detail }: { detail: MatchDetail }) {
  const form = useMatchRecentForm(detail.matchId)
  const byId = new Map((form.data?.players ?? []).map((p) => [p.playerId, p]))

  return (
    <section aria-labelledby="tennis-match-form">
      <h2 id="tennis-match-form" className="tennis-match-section">Recent form · last 5, box scores</h2>
      {form.isLoading ? (
        <div className="tennis-match-empty">Loading recent form...</div>
      ) : form.isError ? (
        <div className="tennis-match-empty">Recent form could not be loaded.</div>
      ) : (
        <div className="tennis-match-form-grid">
          <FormCard name={detail.p1.name} form={byId.get(detail.p1.playerId)} />
          <FormCard name={detail.p2.name} form={byId.get(detail.p2.playerId)} />
        </div>
      )}
    </section>
  )
}
