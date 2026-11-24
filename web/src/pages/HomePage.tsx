import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { HomeGaps } from '~/components/home/HomeGaps'
import { HomeRecords } from '~/components/home/HomeRecords'
import { HomeSportCard } from '~/components/home/HomeSportCard'
import ErrorState from '~/components/shared/ErrorState'
import PageHead from '~/components/shared/PageHead'
import { useHomeData } from '~/hooks/useHomeData'
import { gapTabs, gapsBody, parseGapKind, parseGapTab, todayStatus, type GapKind, type GapTabKey, type TodayStatus } from '~/utils/home'
import '~/components/home/home.css'

function Heading({ title, note }: { title: string, note: string }) {
  return <h2 className="home-section-title">{title} <small>{note}</small></h2>
}

function TodayLine({ status }: { status: TodayStatus }) {
  return <>{status.when}<span className={status.pending ? 'home-status__pending' : undefined}>{status.refreshed}</span></>
}

function homeHref(tab: GapTabKey, view: GapKind): string {
  const query = new URLSearchParams()
  if (tab !== 'all') query.set('gaps', tab)
  if (view === 'ml') query.set('kind', view)
  return query.size === 0 ? '/' : `/?${query}`
}

export default function HomePage() {
  const home = useHomeData()
  const [params] = useSearchParams()
  const selected = parseGapTab(params.get('gaps'))
  const kind = parseGapKind(params.get('kind'))
  const tabs = useMemo(() => gapTabs(home.sports, home.now), [home.sports, home.now])
  const body = useMemo(() => gapsBody(selected, home.sports, kind), [selected, home.sports, kind])
  const tabHref = useCallback((key: GapTabKey) => homeHref(key, kind), [kind])
  const kindHref = useCallback((view: GapKind) => homeHref(selected, view), [selected])

  if (home.failed) return <ErrorState error={new Error('No sport could be loaded.')} onRetry={() => home.sports.forEach(sport => sport.retry())} />
  return <div className="page-shell"><div className="page-container is-wide">
    <PageHead title="Today" meta={<TodayLine status={todayStatus(home.now, home.refreshedAt)} />} />
    <h2 className="home-section-title">Slates</h2>
    <div className="home-cards">
      {home.cards.map(card => <HomeSportCard key={card.sport} card={card} onRetry={card.retry} />)}
    </div>
    <Heading title="Largest gaps across sports" note="reference only, not picks" />
    <HomeGaps tabs={tabs} selected={selected} kind={kind} tabHref={tabHref} kindHref={kindHref} body={body} />
    <Heading title="Model records" note="published track records, per sport" />
    <HomeRecords records={home.records} />
  </div></div>
}
