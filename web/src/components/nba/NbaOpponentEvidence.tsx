import type { NbaTeamStatsContext } from '~/types/nba'
import { nbaOpponentContext, nbaTeamRateText } from '~/utils/nbaTeamStats'

interface Props {
  context: NbaTeamStatsContext | null
  team: string | null
  market: string
}

export function NbaOpponentEvidence({ context, team, market }: Props) {
  const opponent = nbaOpponentContext(context, team, market)
  if (opponent.kind === 'unavailable') return <section className="nba-prop-evidence__section" aria-label="Opponent team context">
    <h4>Opponent context</h4>
    <p>{opponent.message}</p>
  </section>
  const text = nbaTeamRateText(opponent.rate, opponent.completedGames)
  return <section className="nba-prop-evidence__section" aria-label="Opponent team context">
    <h4>Opponent context</h4>
    {opponent.rate.perGame === null
      ? <p>{opponent.opponent} allowed {opponent.measure} unavailable.</p>
      : <><p>{opponent.opponent} allows <strong>{text.value} {opponent.measure}/game</strong>.</p>
        <p>{text.rank} (1 = fewest allowed).</p></>}
    <p>{text.sample}.{text.notes.length > 0 && ` ${text.notes.join('. ')}.`}</p>
    {opponent.completedGames === 0 && <p>No earlier regular-season games this season.</p>}
    <p>{opponent.season}-{String(opponent.season + 1).slice(-2)} regular season, before <time dateTime={opponent.beforeDate}>{opponent.beforeDate}</time> (Eastern date).</p>
    <p>Stored player box-score totals, including overtime. Team context only, not a player projection.
      {market === 'rebounds' && ' Rebounds exclude team-only rebounds.'}</p>
  </section>
}
