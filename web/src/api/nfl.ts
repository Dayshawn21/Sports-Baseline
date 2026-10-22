import client from './client'
import type {
  NflCurrentWeek, NflGameContext, NflGameDetail, NflGameNotesResponse, NflLineOnlyProps, NflModelClv, NflModelFit, NflModelPropLines,
  NflModelRanking, NflRankingModelVersion,
  NflPlayerDetail, NflSlateResponse, NflLineOnlyBoard,
} from '~/types/nfl'
import { rankingParams } from '~/utils/nflTrackRecord'

// The hosted demo builds a cold week in about 34 s (2026-10-16), and a second week
// waits for the first, since the API builds one at a time.
const SLATE_TIMEOUT_MS = 90_000

export async function fetchNflSlate(season: number, week: number): Promise<NflSlateResponse> {
  const { data } = await client.get<NflSlateResponse>('/nfl/slate', {
    params: { season, week },
    timeout: SLATE_TIMEOUT_MS,
  })
  return data
}

export async function fetchNflGameNotes(season: number, week: number): Promise<NflGameNotesResponse> {
  const { data } = await client.get<NflGameNotesResponse>('/nfl/game-notes', { params: { season, week } })
  return data
}

export async function fetchNflCurrentWeek(): Promise<NflCurrentWeek> {
  const { data } = await client.get<NflCurrentWeek>('/nfl/current-week')
  return data
}

export async function fetchNflGame(gameId: number): Promise<NflGameDetail> {
  const { data } = await client.get<NflGameDetail>(`/nfl/games/${gameId}`)
  return data
}

export async function fetchNflGameContext(gameId: number): Promise<NflGameContext> {
  const { data } = await client.get<NflGameContext>(`/nfl/games/${gameId}/context`)
  return data
}

export async function fetchNflLineOnlyProps(gameId: number): Promise<NflLineOnlyProps> {
  const { data } = await client.get<NflLineOnlyProps>(`/nfl/games/${gameId}/line-only-props`)
  return data
}

export async function fetchNflWeekLineOnlyProps(season: number, week: number): Promise<NflLineOnlyBoard> {
  const { data } = await client.get<NflLineOnlyBoard>('/nfl/line-only-props', { params: { season, week } })
  return data
}

export async function fetchNflPlayer(playerId: number): Promise<NflPlayerDetail> {
  const { data } = await client.get<NflPlayerDetail>(`/nfl/players/${playerId}`)
  return data
}

export async function fetchNflModelRanking(season: number, modelVersion?: NflRankingModelVersion): Promise<NflModelRanking> {
  const { data } = await client.get<NflModelRanking>('/nfl/model/ranking', { params: rankingParams(season, modelVersion) })
  return data
}

// A cold load replays the slate for every graded week: 22 s alone and 46 s beside
// the page's other sections on 2026-09-30, past the shared client's 30 s timeout.
const PROP_LINES_TIMEOUT_MS = 90_000

export async function fetchNflModelPropLines(season: number): Promise<NflModelPropLines> {
  const { data } = await client.get<NflModelPropLines>('/nfl/model/prop-lines', {
    params: { season },
    timeout: PROP_LINES_TIMEOUT_MS,
  })
  return data
}

export async function fetchNflModelClv(season: number): Promise<NflModelClv> {
  const { data } = await client.get<NflModelClv>('/nfl/model/game-line-clv', { params: { season } })
  return data
}

export async function fetchNflModelFit(): Promise<NflModelFit> {
  const { data } = await client.get<NflModelFit>('/nfl/model/over-probability-fit')
  return data
}
