import type { ReactNode } from 'react'
import NflGameLineClv from '~/components/nfl/model/NflGameLineClv'
import NflLineGrading from '~/components/nfl/model/NflLineGrading'
import { NflOverProbabilityFit, NflOverProbabilityForward } from '~/components/nfl/model/NflOverProbability'
import NflRankingSlices from '~/components/nfl/model/NflRankingSlices'
import LoadingState from '~/components/shared/LoadingState'
import ModelSection from '~/components/shared/ModelSection'
import SportViewSwitch from '~/components/shared/SportViewSwitch'
import StatChip from '~/components/shared/StatChip'
import { useNflCurrentWeek } from '~/hooks/useNfl'
import { useNflModelClv, useNflModelFit, useNflModelPropLines, useNflModelRanking } from '~/hooks/useNflModelTrackRecord'
import type { NflModelClv, NflModelRanking } from '~/types/nfl'
import { fmtDateCT, fmtTimeCT } from '~/utils/format'
import { summaryCounts } from '~/utils/nflTrackRecord'
import './nfl-model.css'

function Summary({ ranking, clv }: { ranking: NflModelRanking | undefined, clv: NflModelClv | undefined }) {
  const counts = summaryCounts(ranking, clv)
  const verdictLabel = counts.gameLinePasses ? `Game-line verdicts, ${counts.gameLinePasses}` : 'Game-line verdicts'
  return <section className="page-head__stats nfl-model__stats" aria-label="Summary">
    <StatChip value={counts.slicesAdopted} label="Prop slices adopted" />
    <StatChip value={counts.gameLineVerdicts} label={verdictLabel} />
    <StatChip value={counts.lastSettledWeek} label="Last settled week" />
    <StatChip value={ranking?.modelVersion ?? '—'} label="Projection version" />
  </section>
}

function Heading({ title, children }: { title: string, children: ReactNode }) {
  return <h2 className="nfl-model-heading">{title} <small>{children}</small></h2>
}

export default function NflModelPage() {
  const currentWeek = useNflCurrentWeek()
  const season = currentWeek.data?.season ?? null
  const ranking = useNflModelRanking(season)
  const clv = useNflModelClv(season)
  const lines = useNflModelPropLines(season)
  const fit = useNflModelFit()
  const gradedAt = ranking.data?.gradedAt

  if (currentWeek.isLoading) return <LoadingState message="Finding the NFL season..." />
  return <div className="page-shell nfl-model"><div className="page-container is-wide">
    <header className="nfl-model__head">
      <div>
        <div className="unified-eyebrow">NFL · Model{season !== null && <> · {season}</>}</div>
        <h1 className="unified-page-title">Track Record</h1>
        <p className="unified-page-subtitle">
          How the NFL models grade against the lines they have to beat. Gray unless a result clears its baseline by 2 SE.
          {gradedAt && <> Last graded {fmtDateCT(gradedAt)} {fmtTimeCT(gradedAt)}.</>}
        </p>
      </div>
      <SportViewSwitch sport="nfl" />
    </header>
    {season === null
      ? <div className="model-section-empty nfl-model__none">No NFL regular-season games are loaded, so there is no season to grade.</div>
      : <>
        <Summary ranking={ranking.data} clv={clv.data} />
        <Heading title="Forward ranking check">27j · frozen pre-kickoff predictions · decides 27h</Heading>
        <ModelSection query={ranking} loading="Grading frozen predictions...">
          {(data) => <NflRankingSlices data={data} />}
        </ModelSection>
        <Heading title="PrizePicks line grading">27a · standard lines · replays today's code</Heading>
        <ModelSection query={lines} loading="Replaying the slate for every graded week; the first load can take up to a minute...">
          {(data) => <NflLineGrading data={data} />}
        </ModelSection>
        <Heading title="Game-line CLV">28 · does the close move toward the model from the entry line?</Heading>
        <ModelSection query={clv} loading="Grading game lines...">
          {(data) => <NflGameLineClv data={data} />}
        </ModelSection>
        <Heading title="P(over) calibration">27g · display only</Heading>
        <div className="nfl-model-grid">
          <ModelSection query={fit} loading="Loading the 27g fit...">
            {(data) => <NflOverProbabilityFit data={data} />}
          </ModelSection>
          <ModelSection query={lines} loading="Waiting on the line grading above...">
            {(data) => <NflOverProbabilityForward data={data} />}
          </ModelSection>
        </div>
      </>}
  </div></div>
}
