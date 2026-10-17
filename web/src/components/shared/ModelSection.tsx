import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import ErrorState from '~/components/shared/ErrorState'
import './model-section.css'

interface Props<T> {
  query: UseQueryResult<T>
  loading: string
  children: (data: T) => ReactNode
}

/** One section's own loading and error state, so a slow grading query never blanks a track record page. */
export default function ModelSection<T>({ query, loading, children }: Props<T>) {
  if (query.isLoading) return <div className="model-section-empty">{loading}</div>
  if (query.isError || !query.data) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <>{children(query.data)}</>
}
