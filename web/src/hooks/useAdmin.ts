import { useSyncExternalStore } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchAdminSession, fetchFlaggedPlayers, fetchPlayerElo, fetchPlayerStats, setPlayerElo } from '~/api/admin'
import type {
  FetchEloRequest,
  FetchEloResponse,
  FetchStatsRequest,
  FetchStatsResponse,
  SetEloRequest,
  SetEloResponse,
} from '~/types/admin'
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

const FLAGGED_KEY = ['admin', 'flagged']

export function useFlaggedPlayers() {
  return useQuery({
    queryKey: FLAGGED_KEY,
    queryFn: fetchFlaggedPlayers,
    staleTime: 60 * 1000,
  })
}

export interface PlayerAction<P> {
  playerId: number
  payload: P
}

interface ActionHandlers<R> {
  onSuccess: (result: R, playerId: number) => void
  onError: () => void
}

/** A player fix that refreshes the flagged list once it lands; `saved` says whether it did. */
function usePlayerAction<P, R>(
  run: (playerId: number, payload: P) => Promise<R>,
  saved: (result: R) => boolean,
  { onSuccess, onError }: ActionHandlers<R>,
) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ playerId, payload }: PlayerAction<P>) => run(playerId, payload),
    onSuccess: (result, { playerId }) => {
      if (saved(result)) qc.invalidateQueries({ queryKey: FLAGGED_KEY })
      onSuccess(result, playerId)
    },
    onError,
  })
}

export function useFetchPlayerStats(handlers: ActionHandlers<FetchStatsResponse>) {
  return usePlayerAction<FetchStatsRequest, FetchStatsResponse>(
    fetchPlayerStats, result => result.success, handlers,
  )
}

export function useFetchPlayerElo(handlers: ActionHandlers<FetchEloResponse>) {
  return usePlayerAction<FetchEloRequest, FetchEloResponse>(
    fetchPlayerElo, result => result.success, handlers,
  )
}

export function useSetPlayerElo(handlers: ActionHandlers<SetEloResponse>) {
  return usePlayerAction<SetEloRequest, SetEloResponse>(
    setPlayerElo, () => true, handlers,
  )
}
