import NflRankingSlices from '~/components/nfl/model/NflRankingSlices'
import ModelSection from '~/components/shared/ModelSection'
import SportViewSwitch from '~/components/shared/SportViewSwitch'
import StatChip from '~/components/shared/StatChip'
import { useNbaModelRanking } from '~/hooks/useNba'
import { fmtDateCT, fmtTimeCT } from '~/utils/format'
import { isNotFound } from '~/utils/httpError'
import { nbaModelSummary } from '~/utils/nbaModel'
import './nfl-model.css'
import './nba-model.css'

export default function NbaModelPage() {
  const ranking = useNbaModelRanking()
  const summary = nbaModelSummary(ranking.data)
  const season = ranking.data?.season
  const gradedAt = ranking.data?.gradedAt

  return <div className="page-shell nfl-model"><div className="page-container is-wide">
    <header className="nfl-model__head">
      <div>
        <div className="unified-eyebrow">NBA · Model{season !== undefined && <> · {season}</>}</div>
        <h1 className="unified-page-title">Track Record</h1>
        <p className="unified-page-subtitle">
          How the NBA prop model grades against PrizePicks' break-evens. Gray until a slice's verdict is decided.
          {gradedAt && <> Last graded {fmtDateCT(gradedAt)} {fmtTimeCT(gradedAt)}.</>}
        </p>
      </div>
      <SportViewSwitch sport="nba" />
    </header>
    {isNotFound(ranking.error)
      ? <div className="model-section-empty nfl-model__none">No NBA regular-season games are loaded, so there is no season to grade.</div>
      : <>
        <section className="page-head__stats nfl-model__stats nba-model__stats" aria-label="Summary">
          <StatChip value={summary.slicesAdopted} label="Prop slices adopted" />
          <StatChip value={summary.lastSettledWeek} label="Last settled week" />
          <StatChip value={summary.projectionVersion} label="Projection version" />
          <StatChip value={summary.overProbabilityVersion} label="P(over) version" />
        </section>
        <h2 className="nfl-model-heading">Forward ranking check <small>20g4 · frozen pre-tip predictions · 27i's rule</small></h2>
        <ModelSection query={ranking} loading="Grading frozen predictions...">
          {(data) => <NflRankingSlices data={data} />}
        </ModelSection>
      </>}
  </div></div>
}
