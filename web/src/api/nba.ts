import client from './client'
import type { NbaGameDetail, NbaLineOnlyProps, NbaPlayerProps, NbaPropBoardResponse, NbaProps, NbaSlateGapsResponse, NbaSlateResponse } from '~/types/nba'
import type { PropRankingRecord } from '~/types/propRanking'

/** A null date lets the API choose: today, else the next date with games. */
export async function fetchNbaSlate(date: string | null): Promise<NbaSlateResponse> {
  const { data } = await client.get<NbaSlateResponse>('/nba/slate', { params: date === null ? {} : { date } })
  return data
}

/** No limit keeps the API's default digest size, which the slate page relies on. */
export async function fetchNbaSlateGaps(date: string, limit?: number): Promise<NbaSlateGapsResponse> {
  const { data } = await client.get<NbaSlateGapsResponse>('/nba/slate/gaps', { params: limit === undefined ? { date } : { date, limit } })
  return data
}

export async function fetchNbaGame(gameId: number): Promise<NbaGameDetail> {
  const { data } = await client.get<NbaGameDetail>(`/nba/games/${gameId}`)
  return data
}

export async function fetchNbaLineOnlyProps(gameId: number): Promise<NbaLineOnlyProps> {
  const { data } = await client.get<NbaLineOnlyProps>(`/nba/games/${gameId}/line-only-props`)
  return data
}

export async function fetchNbaProps(gameId: number): Promise<NbaProps> {
  const { data } = await client.get<NbaProps>(`/nba/games/${gameId}/props`)
  return data
}

/** A null date lets the API choose the board's default date. */
export async function fetchNbaPlayerProps(playerId: number, date: string | null): Promise<NbaPlayerProps> {
  const { data } = await client.get<NbaPlayerProps>(`/nba/players/${playerId}/props`, { params: date === null ? {} : { date } })
  return data
}

export async function fetchNbaPropBoard(date: string | null): Promise<NbaPropBoardResponse> {
  const { data } = await client.get<NbaPropBoardResponse>('/nba/props', { params: date === null ? {} : { date } })
  return data
}

/** The current NBA season's ranking check; the API picks the season and 404s when none is loaded. */
export async function fetchNbaModelRanking(): Promise<PropRankingRecord> {
  const { data } = await client.get<PropRankingRecord>('/nba/model/ranking')
  return data
}
