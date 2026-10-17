import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { MatchDetail, PlayerFormStats } from '~/types/tennis'
import { useMatchOddsHistory } from '~/hooks/useMatchOddsHistory'
import { useMatchRecentForm } from '~/hooks/useMatchRecentForm'
import { usePrizePicksProps } from '~/hooks/useProps'
import { fmtAmerican, fmtPct } from '~/utils/odds'
import { fmtSurface } from '~/utils/format'
import { bookLabel, latestPerBook } from '~/utils/matchOdds'
import { fmtMatchDateYear, isFinished, matchProps, meetingsNote } from '~/utils/tennisMatch'
import { marketLabel } from '~/utils/tennisPropBoard'

function lastName(name: string): string {
  return name.split(/\s+/).filter(Boolean).pop() ?? name
}

function Meetings({ detail }: { detail: MatchDetail }) {
  const counted = detail.h2h.p1Wins + detail.h2h.p2Wins
  const note = meetingsNote(detail.meetings.length, counted)
  return (
    <>
      {detail.meetings.length > 0 && (
        <ul className="tennis-match-meetings">
          {detail.meetings.map((m, i) => (
            <li key={i}>
              <div className="tennis-match-meetings__result">
                <b>{m.winnerSide ? lastName(detail[m.winnerSide].name) : 'Unknown winner'}</b>
                <span>{m.score ?? 'score unavailable'}</span>
              </div>
              <small>
                {[fmtMatchDateYear(m.matchDate), [m.tournament, m.round].filter(Boolean).join(' '), m.surface ? fmtSurface(m.surface) : null]
                  .filter(Boolean).join(' · ')}
              </small>
            </li>
          ))}
        </ul>
      )}
      {note && <p className="tennis-match-aside__note">{note}</p>}
    </>
  )
}

function H2HCard({ detail }: { detail: MatchDetail }) {
  const { h2h } = detail
  const met = h2h.p1Wins + h2h.p2Wins > 0 || detail.meetings.length > 0
  return (
    <div className="tennis-match-card tennis-match-aside">
      <h3>Head to head</h3>
      {!met ? <p className="tennis-match-aside__empty">No previous meetings on record.</p> : (
        <>
          <div className="tennis-match-h2h">
            <div><b>{h2h.p1Wins}</b><span>{lastName(detail.p1.name)}</span></div>
            <small>all surfaces</small>
            <div><b>{h2h.p2Wins}</b><span>{lastName(detail.p2.name)}</span></div>
          </div>
          {detail.surface && h2h.surfaceP1Wins != null && h2h.surfaceP2Wins != null && (
            <div className="tennis-match-kv"><span>{fmtSurface(detail.surface)}</span><span>{h2h.surfaceP1Wins} – {h2h.surfaceP2Wins}</span></div>
          )}
          <Meetings detail={detail} />
        </>
      )}
    </div>
  )
}

function BooksCard({ detail }: { detail: MatchDetail }) {
  const moneyline = useMatchOddsHistory(detail.matchId, 'moneyline')
  const totals = useMatchOddsHistory(detail.matchId, 'total_games')
  const prices = latestPerBook(moneyline.data?.rows ?? [], 'moneyline')
  const lines = new Map(latestPerBook(totals.data?.rows ?? [], 'total_games').map((r) => [r.book, r.line]))
  const books = [...new Set([...prices.map((r) => r.book), ...lines.keys()])]
  const byBook = new Map(prices.map((r) => [r.book, r]))
  return (
    <div className="tennis-match-card tennis-match-aside">
      <h3>{isFinished(detail) ? 'Closing prices' : 'Books now'}</h3>
      {moneyline.isLoading || totals.isLoading ? <p className="tennis-match-aside__empty">Loading prices...</p>
        : books.length === 0 ? <p className="tennis-match-aside__empty">No stored prices for this match.</p> : (
          <table className="tennis-match-table">
            <thead><tr><th>Book</th><th>{lastName(detail.p1.name)}</th><th>{lastName(detail.p2.name)}</th><th>Games</th></tr></thead>
            <tbody>
              {books.map((book) => (
                <tr key={book}>
                  <td>{bookLabel(book)}</td>
                  <td>{fmtAmerican(byBook.get(book)?.p1Odds)}</td>
                  <td>{fmtAmerican(byBook.get(book)?.p2Odds)}</td>
                  <td>{lines.get(book)?.toFixed(1) ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      <p className="tennis-match-aside__note">Newest stored row per book, before the start.</p>
    </div>
  )
}

// Labelled by what ingest computes, not the column names: aces_per_game is aces per
// serve point and break_pct is break points converted (app/ingest/player_stats.py).
const SERVE_ROWS: Array<[string, (s: PlayerFormStats) => number | null, number]> = [
  ['Hold', (s) => s.holdPct, 0],
  ['Ace rate', (s) => s.acesPerGame, 1],
  ['Service pts won', (s) => s.svcPtsWon, 0],
  ['Return pts won', (s) => s.retPtsWon, 0],
  ['BP converted', (s) => s.breakPct, 0],
]

function ServeCard({ detail }: { detail: MatchDetail }) {
  const form = useMatchRecentForm(detail.matchId)
  const stats = new Map((form.data?.players ?? []).map((p) => [p.playerId, p.last52W]))
  const p1 = stats.get(detail.p1.playerId) ?? null
  const p2 = stats.get(detail.p2.playerId) ?? null
  const fmt = (s: PlayerFormStats | null, pick: (s: PlayerFormStats) => number | null, decimals: number) => {
    const value = s ? pick(s) : null
    return value == null ? '—' : fmtPct(value, decimals)
  }
  return (
    <div className="tennis-match-card tennis-match-aside">
      <h3>Serve and return · 52 weeks</h3>
      {!p1 && !p2 ? <p className="tennis-match-aside__empty">No rolling serve or return stats for either player.</p> : (
        <>
          <div className="tennis-match-kv is-head"><span /><span>{lastName(detail.p1.name)} · {lastName(detail.p2.name)}</span></div>
          {SERVE_ROWS.map(([label, pick, decimals]) => (
            <div key={label} className="tennis-match-kv"><span>{label}</span><span>{fmt(p1, pick, decimals)} · {fmt(p2, pick, decimals)}</span></div>
          ))}
        </>
      )}
    </div>
  )
}

const PROPS_SHOWN = 8

function PropsCard({ detail }: { detail: MatchDetail }) {
  const props = usePrizePicksProps()
  const [expanded, setExpanded] = useState(false)
  const all = matchProps(props.data?.props ?? [], detail.matchId)
  const lines = expanded ? all : all.slice(0, PROPS_SHOWN)
  return (
    <div className="tennis-match-card tennis-match-aside">
      <h3>Props on this match</h3>
      {props.isLoading ? <p className="tennis-match-aside__empty">Loading props...</p>
        : lines.length === 0 ? <p className="tennis-match-aside__empty">No PrizePicks lines are linked to this match.</p> : (
          <div className="tennis-match-props">
            {lines.map((p) => (
              <Link key={p.id} to="/tennis/board">
                <span><b>{lastName(p.playerName ?? '')}</b> {marketLabel(p.statType)}</span>
                <span className="tennis-match-props__right">
                  <span className="tennis-match-props__line">{p.line ?? '—'}</span>
                  {p.oddsType && p.oddsType !== 'standard' && <span className={`tennis-match-props__type is-${p.oddsType}`}>{p.oddsType}</span>}
                  {p.confidence && <span className={`tennis-tier is-${p.confidence.toLowerCase()}`}>{p.recommendation ? `${p.recommendation} · ` : ''}{p.confidence}</span>}
                </span>
              </Link>
            ))}
          </div>
        )}
      {all.length > PROPS_SHOWN && (
        <button type="button" className="tennis-match-aside__more" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show fewer' : `Show all ${all.length} lines`}
        </button>
      )}
    </div>
  )
}

export default function MatchSidebar({ detail }: { detail: MatchDetail }) {
  return (
    <aside className="tennis-match-sidebar" aria-label="Match context">
      <H2HCard detail={detail} />
      <BooksCard detail={detail} />
      <ServeCard detail={detail} />
      <PropsCard detail={detail} />
    </aside>
  )
}
