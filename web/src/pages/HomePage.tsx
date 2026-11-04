import { useSearchParams } from 'react-router-dom'
import { HomeGaps } from '~/components/home/HomeGaps'
import { HomeRecords } from '~/components/home/HomeRecords'
import { HomeSportCard } from '~/components/home/HomeSportCard'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import { useHomeData } from '~/hooks/useHomeData'
import { gapTabs, gapsBody, parseGapTab, todayStatus, type GapTabKey } from '~/utils/home'
import '~/components/home/home.css'

function Heading({ title, note }: { title: string, note: string }) {
  return <h2 className="home-section-title">{title} <small>{note}</small></h2>
}

export default function HomePage() {
  const home = useHomeData()
  const [params] = useSearchParams()
  const selected = parseGapTab(params.get('gaps'))
  const hrefFor = (key: GapTabKey) => key === 'all' ? '/' : `/?gaps=${key}`

  if (home.loading) return <LoadingState message="Loading today..." />
  if (home.failed) return <ErrorState error={new Error('No sport could be loaded.')} onRetry={() => home.sports.forEach(sport => sport.retry())} />
  return <div className="page-shell"><div className="page-container is-wide">
    <PageHead title="Today" meta={todayStatus(home.now, home.refreshedAt)} />
    <h2 className="home-section-title">Slates</h2>
    <div className="home-cards">
      {home.cards.map(card => <HomeSportCard key={card.sport} card={card} onRetry={card.retry} />)}
    </div>
    <Heading title="Largest gaps across sports" note="reference only, not picks" />
    <HomeGaps tabs={gapTabs(home.sports, home.now)} selected={selected} hrefFor={hrefFor} body={gapsBody(selected, home.sports)} />
    <Heading title="Model records" note="published track records, per sport" />
    <HomeRecords records={home.records} />
  </div></div>
}
