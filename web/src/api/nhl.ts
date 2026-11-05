import client from './client'
import type { PropRankingRecord } from '~/types/propRanking'
import type { NhlGameDetail, NhlLineOnlyProps, NhlPlayerProps, NhlPropBoardResponse, NhlSlateResponse } from '~/types/nhl'

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

export async function fetchNhlPlayerProps(playerId: number, date: string | null): Promise<NhlPlayerProps> {
  const { data } = await client.get<NhlPlayerProps>(`/nhl/players/${playerId}/props`, { params: date === null ? {} : { date } })
  return data
}

export async function fetchNhlPropBoard(date: string | null): Promise<NhlPropBoardResponse> {
  const { data } = await client.get<NhlPropBoardResponse>('/nhl/props', { params: date === null ? {} : { date } })
  return data
}

/** The current NHL season's ranking check; the API picks the season and 404s when none is loaded. */
export async function fetchNhlModelRanking(): Promise<PropRankingRecord> {
  const { data } = await client.get<PropRankingRecord>('/nhl/model/ranking')
  return data
}
