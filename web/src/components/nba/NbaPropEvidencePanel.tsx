import type { NbaLineOnlyRow } from '~/utils/nbaLineOnly'
import type { NbaInjuryReport } from '~/types/nba'
import { NbaInjuryEvidence } from '~/components/nba/NbaInjury'
import { nbaMarketLabel, nbaRecentValueLabel } from '~/utils/nbaLineOnly'
import { nbaPropFlagText, signedGap, type NbaPropCard } from '~/utils/nbaProps'

interface HeaderProps {
  playerName: string
  position: string | null
  team: string | null
  market: string
}

function Header({ playerName, position, team, market }: HeaderProps) {
  return <header className="nba-prop-evidence__head">
    <span className="nba-prop-table__team" aria-hidden="true">{team ?? '--'}</span>
    <span>
      <h3>{playerName}</h3>
      <p>{position ? `${position} · ` : ''}{nbaMarketLabel(market)}</p>
    </span>
  </header>
}

function Recent({ market, recent }: { market: string, recent: NbaLineOnlyRow['recent'] }) {
  return <section className="nba-prop-evidence__section">
    <h4>Recent games <small>newest first</small></h4>
    {recent.length ? <div className="nba-prop-evidence__recent">
      {recent.map((game, index) => <div key={`${game.gameDate}-${index}`}>
        <span>{game.gameDate}</span>
        <span>vs {game.opponent ?? '--'}</span>
        <b>{nbaRecentValueLabel(market, game.value)}</b>
      </div>)}
    </div> : <p className="nba-prop-evidence__empty">No earlier games.</p>}
  </section>
}

interface InjuryContext {
  injuryReport: NbaInjuryReport
  startUtc: string | null
}

interface ModelledProps extends InjuryContext {
  kind: 'modelled'
  market: string
  row: NbaPropCard
  modelVersion: string
}

interface LineOnlyProps extends InjuryContext {
  kind: 'line-only'
  market: string
  row: NbaLineOnlyRow
}

type Props = ModelledProps | LineOnlyProps

function Modelled({ row, market, modelVersion, injuryReport, startUtc }: Omit<ModelledProps, 'kind'>) {
  return <>
    <Header playerName={row.playerName} position={row.position} team={row.team} market={market} />
    <p className="nba-prop-evidence__caveat">Reference projection only. No pick, rank, or signal.</p>
    <NbaInjuryEvidence injury={row.injury} report={injuryReport} startUtc={startUtc} now={new Date()} />
    <dl className="nba-prop-evidence__summary">
      <div><dt>Main line</dt><dd>{row.main.line}</dd></div>
      <div><dt>Projection</dt><dd>{row.projectionRow?.projection ?? '--'}</dd></div>
      <div><dt>Gap</dt><dd>{row.projectionRow?.gap ?? '--'}</dd></div>
      <div><dt>P(over)</dt><dd>{row.projectionRow?.pOver ?? '--'}</dd></div>
    </dl>
    <section className="nba-prop-evidence__section">
      <h4>PrizePicks rungs</h4>
      <div className="nba-prop-evidence__rungs is-modelled">
        <span>Line</span><span>Payout</span><span>Gap</span><span>P(over)</span><span>P(under)</span><span>Note</span>
        {row.rungs.map((rung, index) => <div className="nba-prop-evidence__rung" key={`${rung.line}-${rung.oddsType}-${index}`}>
          <b data-label="Line">{rung.line}</b><span data-label="Payout">{rung.oddsType ?? '--'}</span>
          <span data-label="Gap">{rung.gap === null ? '--' : signedGap(rung.gap)}</span>
          <span data-label="P(over)">{rung.pOver === null ? '--' : `${Math.round(rung.pOver * 100)}%`}</span>
          <span data-label="P(under)">{rung.pUnder === null ? '--' : `${Math.round(rung.pUnder * 100)}%`}</span>
          <span data-label="Note">{rung.flags.length ? rung.flags.map(nbaPropFlagText).join(' · ') : '--'}</span>
        </div>)}
      </div>
    </section>
    <section className="nba-prop-evidence__section">
      <h4>Sample</h4>
      <p>{row.gamesInSample} games · {row.priorMinutes === null ? '--' : `${row.priorMinutes.toFixed(1)} avg minutes`} · {modelVersion}</p>
      {row.flagText && <p>{row.flagText}</p>}
    </section>
    <Recent market={market} recent={row.recent} />
  </>
}

function LineOnly({ row, market, injuryReport, startUtc }: Omit<LineOnlyProps, 'kind'>) {
  return <>
    <Header playerName={row.playerName} position={row.position} team={row.team} market={market} />
    <p className="nba-prop-evidence__caveat">Recent results only. This market is not modelled.</p>
    <NbaInjuryEvidence injury={row.injury} report={injuryReport} startUtc={startUtc} now={new Date()} />
    <section className="nba-prop-evidence__section">
      <h4>PrizePicks rungs</h4>
      <div className="nba-prop-evidence__rungs">
        <span>Line</span><span>Payout</span>
        {row.rungs.map((rung, index) => <div className="nba-prop-evidence__rung" key={`${rung.line}-${rung.oddsType}-${index}`}>
          <b data-label="Line">{rung.line}</b><span data-label="Payout">{rung.oddsType ?? '--'}</span>
        </div>)}
      </div>
    </section>
    <Recent market={market} recent={row.recent} />
  </>
}

export default function NbaPropEvidencePanel(props: Props) {
  return <div className="nba-prop-evidence">
    {props.kind === 'modelled'
      ? <Modelled row={props.row} market={props.market} modelVersion={props.modelVersion} injuryReport={props.injuryReport} startUtc={props.startUtc} />
      : <LineOnly row={props.row} market={props.market} injuryReport={props.injuryReport} startUtc={props.startUtc} />}
  </div>
}
