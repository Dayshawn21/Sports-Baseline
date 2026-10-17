import { Link, useParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import MatchHeader from '~/components/tennis/match/MatchHeader'
import MatchComponents from '~/components/tennis/match/MatchComponents'
import MatchHero from '~/components/tennis/match/MatchHero'
import MatchOddsChart from '~/components/tennis/match/MatchOddsChart'
import MatchRecentForm from '~/components/tennis/match/MatchRecentForm'
import MatchSidebar from '~/components/tennis/match/MatchSidebar'
import { useMatchDetail } from '~/hooks/useMatchDetail'
import { isNotFound } from '~/utils/httpError'
import { parseMatchId } from '~/utils/tennisMatch'
import './tennis-match.css'

function BackLink() {
  return <Link className="tennis-match-crumb" to="/">← Tennis slate</Link>
}

function NotFound() {
  return (
    <div className="page-shell tennis-match"><div className="page-container is-wide">
      <BackLink />
      <div className="tennis-match-empty is-page">
        That match is not in the database. It may have been removed on re-ingest, or the link is wrong.
      </div>
    </div></div>
  )
}

export default function TennisMatchPage() {
  const matchId = parseMatchId(useParams().matchId)
  const detail = useMatchDetail(matchId)

  if (matchId == null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <LoadingState message="Loading match..." />
  if (detail.isError || !detail.data) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />

  const data = detail.data
  return (
    <div className="page-shell tennis-match"><div className="page-container is-wide">
      <BackLink />
      <MatchHeader detail={data} />
      <div className="tennis-match-layout">
        <section className="tennis-match-main">
          <MatchHero detail={data} />
          <MatchComponents detail={data} />
          <MatchOddsChart detail={data} />
          <MatchRecentForm detail={data} />
        </section>
        <MatchSidebar detail={data} />
      </div>
    </div></div>
  )
}
