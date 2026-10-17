import { useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAdminSession } from '~/api/admin'
import { sessionAdminKey } from '~/utils/adminAuth'
import { retryUnlessAuthOrLimited } from '~/utils/httpError'

export function useAdminKey(): string | null {
  return useSyncExternalStore(sessionAdminKey.subscribe, sessionAdminKey.read, () => null)
}

export function useAdminSession() {
  const signedIn = useAdminKey() !== null
  const query = useQuery({
    queryKey: ['admin', 'session', { signedIn }],
    queryFn: fetchAdminSession,
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: retryUnlessAuthOrLimited,
  })
  return { ...query, signedIn }
}
