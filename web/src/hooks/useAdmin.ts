import { useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAdminSession } from '~/api/admin'
import { sessionAdminKey } from '~/utils/adminAuth'
import { retryUnlessAuthOrLimited } from '~/utils/httpError'

export function useAdminKey(): string | null {
  return useSyncExternalStore(sessionAdminKey.subscribe, sessionAdminKey.read, () => null)
}

/**
 * Whether the owner's view is on: signed in with the admin key, or a local dev build.
 * It shows the Admin nav (37a) and the diagnostics visitors never see, such as tennis quality flags.
 */
export function useAdminView(): boolean {
  return useAdminKey() !== null || import.meta.env.DEV
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
