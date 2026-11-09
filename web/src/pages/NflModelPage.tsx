import type { ReactNode } from 'react'
import NflGameLineClv from '~/components/nfl/model/NflGameLineClv'
import NflLineGrading from '~/components/nfl/model/NflLineGrading'
import { NflOverProbabilityFit, NflOverProbabilityForward } from '~/components/nfl/model/NflOverProbability'
import NflRankingSlices from '~/components/nfl/model/NflRankingSlices'
import NflVolumeRecord from '~/components/nfl/model/NflVolumeRecord'
import LoadingState from '~/components/shared/LoadingState'
import ModelSection from '~/components/shared/ModelSection'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useNflCurrentWeek } from '~/hooks/useNfl'
import { useNflModelClv, useNflModelFit, useNflModelPropLines, useNflModelRanking } from '~/hooks/useNflModelTrackRecord'
import type { NflModelClv, NflModelRanking } from '~/types/nfl'
import { fmtDateCT, fmtTimeCT } from '~/utils/format'
import { NFL_TARGETS_RANKING_MODEL, NFL_VOLUME_RANKING_MODEL, summaryCounts } from '~/utils/nflTrackRecord'
import './nfl-model.css'

function Summary({ ranking, clv }: { ranking: NflModelRanking | undefined, clv: NflModelClv | undefined }) {
  const counts = summaryCounts(ranking, clv)
  const verdictLabel = counts.gameLinePasses ? `Game-line verdicts, ${counts.gameLinePasses}` : 'Game-line verdicts'
  return <section className="page-head__stats nfl-model__stats" aria-label="Summary">
    <StatChip value={counts.slicesAdopted} label="V4 prop slices adopted" />
    <StatChip value={counts.gameLineVerdicts} label={verdictLabel} />
    <StatChip value={counts.lastSettledWeek} label="V4 last settled week" />
    <StatChip value={ranking?.modelVersion ?? '\u2014'} label="V4 projection version" />
  </section>
}

function Heading({ title, children }: { title: string, children: ReactNode }) {
  return <h2 className="nfl-model-heading">{title} <small>{children}</small></h2>
}

export default function NflModelPage() {
  const currentWeek = useNflCurrentWeek()
  const season = currentWeek.data?.season ?? null
  const ranking = useNflModelRanking(season)
  const targets = useNflModelRanking(season, NFL_TARGETS_RANKING_MODEL)
  const volume = useNflModelRanking(season, NFL_VOLUME_RANKING_MODEL)
  const clv = useNflModelClv(season)
  const lines = useNflModelPropLines(season)
  const fit = useNflModelFit()
  const gradedAt = ranking.data?.gradedAt

  if (currentWeek.isLoading) return <LoadingState message="Finding the NFL season..." />
  return <div className="page-shell nfl-model"><div className="page-container is-wide">
    <PageHead
      title="Track record"
      meta={season !== null && <>{season} season{gradedAt && <> · v4 last graded {fmtDateCT(gradedAt)} {fmtTimeCT(gradedAt)}</>}</>}
      stats={season !== null && <Summary ranking={ranking.data} clv={clv.data} />}
    />
    {season === null
      ? <div className="model-section-empty nfl-model__none">No NFL regular-season games are loaded, so there is no season to grade.</div>
      : <>
        <section aria-label="V4 forward ranking check">
          <Heading title="V4 forward ranking check">27j · frozen pre-kickoff predictions · decides 27h</Heading>
          <ModelSection query={ranking} loading="Grading frozen predictions...">
            {(data) => <NflRankingSlices data={data} />}
          </ModelSection>
        </section>
        <section aria-label="Rec Targets forward check">
          <Heading title="Rec Targets forward check">nfl-targets-v1 · reference only</Heading>
          <ModelSection query={targets} loading="Grading frozen Rec Targets predictions...">
            {(data) => <NflRankingSlices data={data} referenceOnly />}
          </ModelSection>
        </section>
        <section aria-label="Volume model forward check">
          <Heading title="Volume model forward check">nfl-volume-v1 · receptions · reference only</Heading>
          <ModelSection query={volume} loading="Grading frozen volume predictions...">
            {(data) => <NflVolumeRecord data={data} />}
          </ModelSection>
        </section>
        <Heading title="PrizePicks line grading">27a · standard lines · replays today's code</Heading>
        <ModelSection query={lines} loading="Replaying the slate for every graded week; the first load can take up to a minute...">
          {(data) => <NflLineGrading data={data} />}
        </ModelSection>
        <p className="nfl-model-note">
          Corrected 2026-11-08: kicker fantasy lines were counted as calls before then. Fantasy scoring has no
          kicking terms, so kickers projected 0 and settled at 0, and every one graded as a winning under
          (160 of the 2026 calls). They are left out until kicker scoring is modelled, which moved fantasy points
          from 56.2% to 50.6% and all calls from 51.1% to 49.5%.
        </p>
        <p className="nfl-model-note">
          Corrected 2026-11-08: kicker fantasy lines now settle on PrizePicks&apos; kicking points (field goals 3, 4
          or 5 by distance, 1 per extra point), not 0. The 184 settled standard kicker lines went from all unders
          to 90 overs and 91 unders, moving fantasy points / standard from 42.4% to 48.0% over. Model calls are
          unchanged: kickers still carry no projection. A missed extra point may cost a point on PrizePicks; that
          would change 3 of these lines.
        </p>
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
