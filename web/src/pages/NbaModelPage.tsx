import NflRankingSlices from '~/components/nfl/model/NflRankingSlices'
import ModelSection from '~/components/shared/ModelSection'
import PageHead from '~/components/shared/PageHead'
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
  const notFound = isNotFound(ranking.error)

  return <div className="page-shell nfl-model"><div className="page-container is-wide">
    <PageHead
      title="Track record"
      meta={season !== undefined && <>{season} season{gradedAt && <> · last graded {fmtDateCT(gradedAt)} {fmtTimeCT(gradedAt)}</>}</>}
      stats={!notFound && <section className="page-head__stats nfl-model__stats nba-model__stats" aria-label="Summary">
        <StatChip value={summary.slicesAdopted} label="Prop slices adopted" />
        <StatChip value={summary.lastSettledWeek} label="Last settled week" />
        <StatChip value={summary.projectionVersion} label="Projection version" />
        <StatChip value={summary.overProbabilityVersion} label="P(over) version" />
      </section>}
    />
    {notFound
      ? <div className="model-section-empty nfl-model__none">No NBA regular-season games are loaded, so there is no season to grade.</div>
      : <>
        <h2 className="nfl-model-heading">Forward ranking check <small>20g4 · frozen pre-tip predictions · 27i's rule</small></h2>
        <ModelSection query={ranking} loading="Grading frozen predictions...">
          {(data) => <NflRankingSlices data={data} />}
        </ModelSection>
      </>}
  </div></div>
}
