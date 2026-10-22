import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import { useNflGameContext } from '~/hooks/useNfl'
import type { NflSlateGame, NflSlateLine } from '~/types/nfl'
import { evidenceAllowedMeasures, evidenceContextGameId, evidenceUsageMeasures, selectedEvidenceContext } from '~/utils/nflEvidenceContext'
import { contextRank } from '~/utils/nflMatchupContext'
import { NflContextMetric } from '~/components/nfl/NflContextMetric'
import '~/components/nfl/nfl-matchup-context.css'

export function NflEvidenceContext({ row, game }: { row: NflSlateLine, game: NflSlateGame | null }) {
  const gameId = evidenceContextGameId(game, row)
  const context = useNflGameContext(gameId)
  const selected = selectedEvidenceContext(context.data, game, row)
  if (gameId === null) return null
  return <section className="nfl-prop-detail__section nfl-evidence-context" aria-label="Historical matchup and usage">
    <h3 className="nfl-evidence-context__heading">Historical usage</h3>
    {context.isLoading && <div role="status"><LoadingState message="Loading historical context..." /></div>}
    {context.isError && <ErrorState error={context.error} onRetry={() => void context.refetch()} />}
    {context.isSuccess && !selected && <p className="nfl-evidence-context__note">No unambiguous current-week roster context is stored for {row.playerName} in this game.</p>}
    {selected && context.data && <>
      <p className="nfl-evidence-context__note">{context.data.season} season through Week {context.data.cutoffWeek}. Recent means the last up to three played games in this window. Full-game history; dates are UTC.</p>
      {selected.player.seasonUsage.teams.length > 1 && <p className="nfl-evidence-context__note">Historical teams: {selected.player.seasonUsage.teams.join(', ')}.</p>}
      <table className="nfl-context-table">
        <caption className="sr-only">{row.playerName}: recent versus season usage with metric-specific observed and eligible games, coverage and dates</caption>
        <colgroup><col className="nfl-context-table__label" /><col /><col /></colgroup>
        <thead><tr><th scope="col">Measure</th><th scope="col">Recent</th><th scope="col">Season</th></tr></thead>
        <tbody>{evidenceUsageMeasures(selected.player.position).map(measure => <tr key={measure.key}>
          <th scope="row">{measure.label}</th>
          <td><NflContextMetric metric={selected.player.recentUsage[measure.key]} share={measure.share} /></td>
          <td><NflContextMetric metric={selected.player.seasonUsage[measure.key]} share={measure.share} /></td>
        </tr>)}</tbody>
      </table>
      <p className="nfl-evidence-context__note">Shares use recorded team targets and all team carries (including QBs) in paired, covered player-games. Snap share is the arithmetic average game fraction. Descriptive context only.</p>
      <OpponentContext row={row} selected={selected} />
    </>}
  </section>
}

function OpponentContext({ row, selected }: {
  row: NflSlateLine, selected: NonNullable<ReturnType<typeof selectedEvidenceContext>>,
}) {
  const measures = evidenceAllowedMeasures(selected.player.position, row.market)
  if (!measures.length) return null
  return <div className="nfl-evidence-context__opponent">
    <h3 className="nfl-evidence-context__heading">{selected.opponent.team} allowed vs {selected.player.position}</h3>
    <p className="nfl-evidence-context__note">Per defense game. Rank 1 = fewest allowed among teams with data.{row.market === 'receiving_targets' ? ' Rec Targets uses receiving context: receptions and receiving yards allowed.' : ''}</p>
    <table className="nfl-context-table">
      <caption className="sr-only">Opponent position production allowed, ranks, metric coverage and dates</caption>
      <thead><tr><th scope="col">Measure</th><th scope="col">{selected.opponent.team} defense</th></tr></thead>
      <tbody>{measures.map(measure => <tr key={measure.key}>
        <th scope="row">{measure.label}</th><td>
          <NflContextMetric metric={selected.opponent.allowed[measure.key]} />
          <small className="nfl-context-rank">{contextRank(selected.opponent.allowed[measure.key])}</small>
        </td>
      </tr>)}</tbody>
    </table>
  </div>
}
