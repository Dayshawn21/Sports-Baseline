import client from './client'
import type {
  AdminSession,
  FetchEloRequest,
  FetchEloResponse,
  FetchStatsRequest,
  FetchStatsResponse,
  FlaggedPlayersResponse,
  SetEloRequest,
  SetEloResponse,
} from '~/types/admin'

export async function fetchAdminSession(): Promise<AdminSession> {
  const { data } = await client.get<AdminSession>('/admin/session')
  return data
}

export async function fetchFlaggedPlayers(): Promise<FlaggedPlayersResponse> {
  const { data } = await client.get<FlaggedPlayersResponse>('/admin/players/flagged')
  return data
}

export async function fetchPlayerStats(
  playerId: number,
  payload: FetchStatsRequest,
): Promise<FetchStatsResponse> {
  const { data } = await client.post<FetchStatsResponse>(
    `/admin/players/${playerId}/fetch-stats`,
    payload,
  )
  return data
}

export async function fetchPlayerElo(
  playerId: number,
  payload: FetchEloRequest,
): Promise<FetchEloResponse> {
  const { data } = await client.post<FetchEloResponse>(
    `/admin/players/${playerId}/fetch-elo`,
    payload,
  )
  return data
}

export async function setPlayerElo(
  playerId: number,
  payload: SetEloRequest,
): Promise<SetEloResponse> {
  const { data } = await client.post<SetEloResponse>(
    `/admin/players/${playerId}/set-elo`,
    payload,
  )
  return data
}
