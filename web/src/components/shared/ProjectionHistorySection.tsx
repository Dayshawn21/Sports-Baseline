import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'

export type ProjectionHistoryView =
  | { kind: 'empty', className: string, message: ReactNode }
  | { kind: 'chart', className: string, toolbar: ReactNode, chart: ReactNode, noteClassName: string, note: string }

interface Props<T> {
  playerName: string
  query: UseQueryResult<T, unknown>
  /** What the sport shows once its history has loaded. */
  children: (data: T) => ProjectionHistoryView
}

/** The heading, query states and card layout every sport's projection history shares. */
export function ProjectionHistorySection<T>({ playerName, query, children }: Props<T>) {
  const heading = <h2 className="nfl-player-section-title">Projection history <small>frozen pregame projections against results</small></h2>
  if (query.isLoading) return <section>{heading}<LoadingState message="Loading projection history..." /></section>
  if (query.isError || !query.data) return <section>{heading}<ErrorState error={query.error} onRetry={() => void query.refetch()} /></section>

  const view = children(query.data)
  if (view.kind === 'empty') return <section>{heading}<div className={view.className}>{view.message}</div></section>
  return <section aria-label={`${playerName} projection history`}>
    {heading}
    <div className={view.className}>
      <div className="nfl-prop-detail__toolbar">{view.toolbar}</div>
      {view.chart}
      <p className={view.noteClassName}>{view.note}</p>
    </div>
  </section>
}
