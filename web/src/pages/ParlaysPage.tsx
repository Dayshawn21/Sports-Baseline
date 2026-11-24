import { useState } from 'react'
import { Select, DatePicker } from 'antd'
import { useBankrollBuilder } from '~/hooks/useBankrollBuilder'
import LoadingState from '~/components/shared/LoadingState'
import ErrorState from '~/components/shared/ErrorState'
import PageHead from '~/components/shared/PageHead'
import StatChip from '~/components/shared/StatChip'
import { useIsMobile } from '~/hooks/useIsMobile'
import { slateDateLabel } from '~/utils/slateDates'
import { TourSection } from '~/components/tennis/parlays/TourSection'
import { splitByTour } from '~/utils/bankrollTours'

export default function ParlaysPage() {
  const isMobile = useIsMobile()
  const [tour, setTour] = useState<string | undefined>()
  const [customDate, setCustomDate] = useState<string | undefined>()

  const params = {
    ...(customDate ? { date: customDate } : {}),
    ...(tour ? { tour } : {}),
  }
  const { data, isLoading, isError, error, refetch } = useBankrollBuilder(
    Object.keys(params).length > 0 ? params : undefined,
  )
  const split = data ? splitByTour(data) : null

  return (
    <div className="page-shell">
      <div className="page-container is-wide">
        <PageHead
          title="Bankroll Builder"
          meta={data ? slateDateLabel(data.date) : undefined}
          stats={data && <div className="page-head__stats">
            <StatChip value={data.singlesCount} label="Singles" />
            <StatChip value={data.parlaysCount} label="Parlays" color="var(--text-primary)" />
          </div>}
        />

        <div className="page-toolbar" style={{ justifyContent: 'flex-end' }}>
          <div className="filter-bar-responsive" style={{ justifyContent: 'flex-end' }}>
            <Select
              style={{ width: isMobile ? '100%' : 130 }}
              placeholder="All Tours"
              allowClear
              value={tour}
              onChange={(v) => setTour(v || undefined)}
              options={[
                { value: 'ATP', label: 'ATP' },
                { value: 'WTA', label: 'WTA' },
              ]}
            />
            <DatePicker
              style={{ width: isMobile ? '100%' : 140 }}
              placeholder="Today"
              onChange={(_, dateStr) => setCustomDate(dateStr as string || undefined)}
              allowClear
            />
            <button
              onClick={() => refetch()}
              style={{
                padding: '6px 16px',
                border: '1px solid var(--border-card)',
                borderRadius: 6,
                background: 'var(--bg-raised)',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                minHeight: 34,
              }}
            >
              Refresh
            </button>
          </div>
        </div>

        {isLoading && <LoadingState />}
        {isError && <ErrorState error={error} onRetry={refetch} />}

        {data && split && (
          <>
            {(split.mainSingles.length > 0 || split.mainParlays.length > 0) && (
              <TourSection
                title="ATP & WTA"
                color="var(--text-primary)"
                singles={split.mainSingles}
                parlays={split.mainParlays}
                isNarrow={isMobile}
              />
            )}

            {(split.challSingles.length > 0 || split.challParlays.length > 0) && (
              <TourSection
                title="Challengers"
                color="var(--challenger-teal)"
                singles={split.challSingles}
                parlays={split.challParlays}
                isNarrow={isMobile}
              />
            )}

            {data.singles.length === 0 && data.parlays.length === 0 && (
              <div style={{
                textAlign: 'center',
                padding: '60px 20px',
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-body)',
                fontSize: 14,
              }}>
                No value picks found for today. Check back closer to match time when odds are available.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
