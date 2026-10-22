import type { ReactNode } from 'react'
import { Tabs } from 'antd'
import { Link, useParams } from 'react-router-dom'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import MatchHeader from '~/components/tennis/match/MatchHeader'
import MatchComponents from '~/components/tennis/match/MatchComponents'
import MatchHero from '~/components/tennis/match/MatchHero'
import MatchOddsChart from '~/components/tennis/match/MatchOddsChart'
import MatchRecentForm from '~/components/tennis/match/MatchRecentForm'
import MatchSidebar from '~/components/tennis/match/MatchSidebar'
import MatchPropsPanel from '~/components/tennis/match/MatchPropsPanel'
import MatchSurfaceContext from '~/components/tennis/match/MatchSurfaceContext'
import MatchWorkloadContext from '~/components/tennis/match/MatchWorkloadContext'
import MatchFreshness from '~/components/tennis/match/MatchFreshness'
import { useMatchDetail } from '~/hooks/useMatchDetail'
import { useMatchView } from '~/hooks/useMatchView'
import { useRegisterDetailTitle } from '~/components/shared/DocumentTitleProvider'
import { isNotFound } from '~/utils/httpError'
import { parseMatchId } from '~/utils/tennisMatch'
import type { MatchDetail } from '~/types/tennis'
import './tennis-match.css'

function BackLink() {
  return <Link className="tennis-match-crumb" to="/">← Tennis slate</Link>
}

function MatchPageState({ children }: { children: ReactNode }) {
  return (
    <div className="page-shell tennis-match"><div className="page-container is-wide">
      <BackLink />
      <PageHead title="Tennis match" />
      {children}
    </div></div>
  )
}

function NotFound() {
  return <MatchPageState><div className="tennis-match-empty is-page">
    That match is not in the database. It may have been removed on re-ingest, or the link is wrong.
  </div></MatchPageState>
}

function MatchSections({ detail: data }: { detail: MatchDetail }) {
  const { view, setView } = useMatchView(data)
  return <Tabs key={data.matchId} className="tennis-match-tabs" activeKey={view.tab}
    onChange={tab => setView({ tab: tab === 'props' ? 'props' : 'analysis' })} destroyOnHidden
    aria-label="Match sections" animated={false} items={[
      { key: 'analysis', label: 'Analysis', children: <div className="tennis-match-layout">
        <section className="tennis-match-main">
          <MatchHero detail={data} />
          <MatchComponents detail={data} />
          <MatchSurfaceContext detail={data} />
          <MatchWorkloadContext detail={data} />
          <MatchFreshness detail={data} />
          <MatchOddsChart detail={data} />
          <MatchRecentForm detail={data} />
        </section>
        <MatchSidebar detail={data} onOpenProps={() => setView({ tab: 'props' })} />
      </div> },
      { key: 'props', label: 'Picks & Props', children: <MatchPropsPanel detail={data} /> },
    ]} />
}

export default function TennisMatchPage() {
  const matchId = parseMatchId(useParams().matchId)
  const detail = useMatchDetail(matchId)
  useRegisterDetailTitle(detail.isSuccess && matchId !== null ? `${detail.data.p1.name} vs ${detail.data.p2.name}` : null)

  if (matchId == null || isNotFound(detail.error)) return <NotFound />
  if (detail.isLoading) return <MatchPageState><LoadingState message="Loading match..." /></MatchPageState>
  if (detail.isError || !detail.data) return <MatchPageState><ErrorState error={detail.error} onRetry={() => void detail.refetch()} /></MatchPageState>

  const data = detail.data
  return (
    <div className="page-shell tennis-match"><div className="page-container is-wide">
      <BackLink />
      <MatchHeader detail={data} />
      <MatchSections key={data.matchId} detail={data} />
    </div></div>
  )
}
