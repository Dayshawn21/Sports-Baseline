import client from './client'
import type { NhlGameDetail, NhlLineOnlyProps, NhlSlateResponse } from '~/types/nhl'

export async function fetchNhlSlate(date: string | null): Promise<NhlSlateResponse> {
  const { data } = await client.get<NhlSlateResponse>('/nhl/slate', { params: date === null ? {} : { date } })
  return data
}

export async function fetchNhlGame(gameId: number): Promise<NhlGameDetail> {
  const { data } = await client.get<NhlGameDetail>(`/nhl/games/${gameId}`)
  return data
}

export async function fetchNhlLineOnlyProps(gameId: number): Promise<NhlLineOnlyProps> {
  const { data } = await client.get<NhlLineOnlyProps>(`/nhl/games/${gameId}/line-only-props`)
  return data
}
