import { Fragment } from 'react'
import type { NflGameNotes, NflTeamStats } from '~/types/nfl'
import { SMALL_SAMPLE_GAMES, TEAM_STAT_ROWS, gamesLabel, rankLabel, statValue } from '~/utils/nflGameNotes'

function sampleLabel(offense: NflTeamStats, defense: NflTeamStats): string {
  const games = [offense, defense].map(stats => `${stats.team} ${gamesLabel(stats) ?? 'no games'}`).join(', ')
  return Math.min(offense.games, defense.games) < SMALL_SAMPLE_GAMES ? `${games} · small sample` : games
}

/** One team's offense beside the other team's defense, so each row reads as the matchup. */
function MatchupTable({ offense, defense }: { offense: NflTeamStats, defense: NflTeamStats }) {
  const played = offense.games > 0 && defense.games > 0
  return <div className="nfl-game-stats__half">
    <h3><b>{offense.team} offense</b> vs {defense.team} defense<small>{sampleLabel(offense, defense)}</small></h3>
    {!played ? <p className="nfl-game-side__empty">Not enough completed games this season</p> : <table>
      <colgroup><col /><col className="is-value" /><col className="is-rank" /><col className="is-value" /><col className="is-rank" /></colgroup>
      <thead><tr><th scope="col" /><th scope="col">{offense.team} off</th><th scope="col" /><th scope="col">{defense.team} def</th><th scope="col" /></tr></thead>
      <tbody>{TEAM_STAT_ROWS.map(row => <tr key={row.label}>
        <th scope="row">{row.label}</th>
        {[offense[row.offense], defense[row.defense]].map((stat, index) => <Fragment key={index}>
          <td>{statValue(stat, row.kind)}</td>
          <td className="is-rank">{rankLabel(stat.rank)}</td>
        </Fragment>)}
      </tr>)}</tbody>
    </table>}
  </div>
}

/** Item 30's team stats as a matchup card. Context only: never changes an edge or its rank. */
export function NflTeamStatsMatchup({ notes }: { notes: NflGameNotes }) {
  return <section className="nfl-game-card nfl-game-stats" aria-label="Team stats">
    <div className="nfl-game-card__head"><h2 className="nfl-game-label">Team stats</h2><span className="nfl-game-side__meta">Season per game · rank of 32 · defense = allowed</span></div>
    <div className="nfl-game-stats__body">
      <MatchupTable offense={notes.awayStats} defense={notes.homeStats} />
      <MatchupTable offense={notes.homeStats} defense={notes.awayStats} />
    </div>
  </section>
}
