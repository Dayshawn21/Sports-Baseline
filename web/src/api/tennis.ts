import client from './client'
import type { BankrollBuilderResponse, BestPicksResponse, MatchDetail, MatchOddsHistory, MatchOddsMarket, MatchRecentFormResponse, ModelPredictionsResponse, ModelPrizePicksLinesResponse, ModelPropTiersResponse, PlayerDetail, PlayerMatches, PlayerProps, PlayerServeReturn, PlayerStats, PredictionsResponse, PropsAuditResponse, PropsResponse } from '~/types/tennis'

export async function fetchPredictionsToday(params?: {
  date?: string
  tour?: string
}): Promise<PredictionsResponse> {
  const { data } = await client.get<PredictionsResponse>('/tennis/predictions/today', {
    params: params ? { match_date: params.date, tour: params.tour } : undefined,
  })
  return data
}

export async function fetchPrizePicksProps(): Promise<PropsResponse> {
  const { data } = await client.get<PropsResponse>('/tennis/props/prizepicks')
  return data
}

export async function fetchPrizePicksPropsAudit(): Promise<PropsAuditResponse> {
  const { data } = await client.get<PropsAuditResponse>('/tennis/props/prizepicks/audit')
  return data
}

export async function fetchDKProps(): Promise<PropsResponse> {
  const { data } = await client.get<PropsResponse>('/tennis/props/dk')
  return data
}

export async function fetchBetProps(): Promise<PropsResponse> {
  const { data } = await client.get<PropsResponse>('/tennis/props/bet')
  return data
}

export async function fetchTopProps(limit = 10, minConfidence = 'LEAN'): Promise<PropsResponse> {
  const { data } = await client.get<PropsResponse>('/tennis/props/top', {
    params: { limit, min_confidence: minConfidence },
  })
  return data
}

export async function fetchBestPicks(params?: {
  date?: string
  tour?: string
}): Promise<BestPicksResponse> {
  const { data } = await client.get<BestPicksResponse>('/tennis/predictions/best-picks', {
    params: params ? { match_date: params.date, tour: params.tour } : undefined,
  })
  return data
}

export async function fetchBankrollBuilder(params?: {
  date?: string
  tour?: string
}): Promise<BankrollBuilderResponse> {
  const { data } = await client.get<BankrollBuilderResponse>('/tennis/bankroll/today', {
    params: params ? { match_date: params.date, tour: params.tour } : undefined,
  })
  return data
}

export async function fetchPlayerStats(
  name: string,
  tour?: string | null,
  surface?: string | null,
): Promise<PlayerStats | null> {
  const params: Record<string, string> = { name }
  if (tour) params.tour = tour
  if (surface) params.surface = surface
  const { data } = await client.get<PlayerStats | null>('/tennis/players/stats', { params })
  return data
}

export async function fetchMatchDetail(matchId: number): Promise<MatchDetail> {
  const { data } = await client.get<MatchDetail>(`/tennis/matches/${matchId}`)
  return data
}

export async function fetchMatchOddsHistory(matchId: number, market: MatchOddsMarket): Promise<MatchOddsHistory> {
  const { data } = await client.get<MatchOddsHistory>(`/tennis/matches/${matchId}/odds-history`, {
    params: { market },
  })
  return data
}

export async function fetchMatchRecentForm(matchId: number): Promise<MatchRecentFormResponse> {
  const { data } = await client.get<MatchRecentFormResponse>(`/tennis/matches/${matchId}/recent-form`)
  return data
}

export async function fetchModelPredictions(modelVersion?: string): Promise<ModelPredictionsResponse> {
  const { data } = await client.get<ModelPredictionsResponse>('/tennis/model/predictions', {
    params: modelVersion ? { model_version: modelVersion } : undefined,
  })
  return data
}

export async function fetchModelPrizePicksLines(): Promise<ModelPrizePicksLinesResponse> {
  const { data } = await client.get<ModelPrizePicksLinesResponse>('/tennis/model/prizepicks-lines')
  return data
}

export async function fetchModelPropTiers(): Promise<ModelPropTiersResponse> {
  const { data } = await client.get<ModelPropTiersResponse>('/tennis/model/prop-tiers')
  return data
}

export async function fetchPlayerDetail(playerId: number): Promise<PlayerDetail> {
  const { data } = await client.get<PlayerDetail>(`/tennis/players/${playerId}`)
  return data
}

export async function fetchPlayerServeReturn(playerId: number): Promise<PlayerServeReturn> {
  const { data } = await client.get<PlayerServeReturn>(`/tennis/players/${playerId}/serve-return`)
  return data
}

export async function fetchPlayerMatches(playerId: number, limit = 20): Promise<PlayerMatches> {
  const { data } = await client.get<PlayerMatches>(`/tennis/players/${playerId}/matches`, { params: { limit } })
  return data
}

export async function fetchPlayerProps(playerId: number): Promise<PlayerProps> {
  const { data } = await client.get<PlayerProps>(`/tennis/players/${playerId}/props`)
  return data
}
