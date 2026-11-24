import client from './client'
import type { PropRankingRecord } from '~/types/propRanking'
import type {
  NhlGameDetail, NhlLineOnlyProps, NhlLineOnlyWireProps, NhlPlayerProps, NhlProjectionHistory, NhlPropBoardResponse, NhlPropBoardWireResponse,
  NhlSlateResponse,
} from '~/types/nhl'
import { nhlJoinProjections } from '~/utils/nhlLineOnly'

export async function fetchNhlSlate(date: string | null): Promise<NhlSlateResponse> {
  const { data } = await client.get<NhlSlateResponse>('/nhl/slate', { params: date === null ? {} : { date } })
  return data
}

export async function fetchNhlGame(gameId: number): Promise<NhlGameDetail> {
  const { data } = await client.get<NhlGameDetail>(`/nhl/games/${gameId}`)
  return data
}

export async function fetchNhlLineOnlyProps(gameId: number): Promise<NhlLineOnlyProps> {
  const { data } = await client.get<NhlLineOnlyWireProps>(`/nhl/games/${gameId}/line-only-props`)
  const { projections, ...props } = data
  return { ...props, lines: nhlJoinProjections(data.lines, projections) }
}

export async function fetchNhlPlayerProps(playerId: number, date: string | null): Promise<NhlPlayerProps> {
  const { data } = await client.get<NhlPlayerProps>(`/nhl/players/${playerId}/props`, { params: date === null ? {} : { date } })
  return data
}

export async function fetchNhlProjectionHistory(playerId: number): Promise<NhlProjectionHistory> {
  const { data } = await client.get<NhlProjectionHistory>(`/nhl/players/${playerId}/projection-history`)
  return data
}

export async function fetchNhlPropBoard(date: string | null): Promise<NhlPropBoardResponse> {
  const { data } = await client.get<NhlPropBoardWireResponse>('/nhl/props', { params: date === null ? {} : { date } })
  return {
    ...data,
    games: data.games.map(({ projections, lines, ...game }) => ({ ...game, lines: nhlJoinProjections(lines, projections) })),
  }
}

/** The current NHL season's ranking check; the API picks the season and 404s when none is loaded. */
export async function fetchNhlModelRanking(): Promise<PropRankingRecord> {
  const { data } = await client.get<PropRankingRecord>('/nhl/model/ranking')
  return data
}
