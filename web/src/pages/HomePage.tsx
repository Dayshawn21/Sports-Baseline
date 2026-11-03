import { HomeHero } from '~/components/home/HomeHero'
import { HomeRecords } from '~/components/home/HomeRecords'
import { HomeStrip } from '~/components/home/HomeStrip'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import PageHead from '~/components/shared/PageHead'
import { useHomeData } from '~/hooks/useHomeData'
import { todayStatus } from '~/utils/home'
import { SPORTS } from '~/utils/sportNav'
import '~/components/home/home.css'

export default function HomePage() {
  const home = useHomeData()
  const lead = home.sports.find(sport => sport.data.sport === home.lead)
  const leadLabel = SPORTS.find(sport => sport.code === home.lead)?.label ?? null

  if (home.loading) return <LoadingState message="Loading today..." />
  if (home.failed) return <ErrorState error={new Error('No sport could be loaded.')} onRetry={() => home.sports.forEach(sport => sport.retry())} />
  return <div className="page-shell"><div className="page-container is-wide">
    <PageHead title="Today" meta={todayStatus(leadLabel, home.now)} />
    <h2 className="home-section-title">Next up</h2>
    {lead
      ? <HomeHero sport={lead} record={home.records.find(record => record.sport === home.lead)} now={home.now} />
      : <div className="home-empty">Nothing scheduled on any slate right now.</div>}
    <h2 className="home-section-title">{lead ? 'Also today' : 'Slates'}</h2>
    <HomeStrip rows={home.strip} />
    <h2 className="home-section-title">Model records</h2>
    <HomeRecords records={home.records} />
  </div></div>
}
