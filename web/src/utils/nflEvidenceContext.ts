import type { NflContextPlayer, NflGameContext, NflMatchupTeam, NflSlateGame, NflSlateLine, NflUsageWindow } from '~/types/nfl'
import { POSITION_ALLOWED_ROWS } from '~/utils/nflMatchupContext'

export interface UsageMeasure {
  key: Exclude<keyof NflUsageWindow, 'teams'>
  label: string
  share: boolean
}

const USAGE_MEASURES: UsageMeasure[] = [
  { key: 'targets', label: 'Targets / game', share: false },
  { key: 'targetShare', label: 'Target share', share: true },
  { key: 'carries', label: 'Carries / game', share: false },
  { key: 'carryShare', label: 'Carry share', share: true },
  { key: 'avgGameSnapShare', label: 'Avg game snap share', share: true },
]

type ContextLine = Pick<NflSlateLine, 'lineId' | 'playerId' | 'market' | 'position'>
type ContextGame = Pick<NflSlateGame, 'gameId' | 'awayTeam' | 'homeTeam'> & { lines: Pick<NflSlateLine, 'lineId' | 'playerId' | 'market'>[] }

export function evidenceUsageMeasures(position: string | null): UsageMeasure[] {
  if (position === 'QB') return USAGE_MEASURES.filter(row => row.key !== 'targets' && row.key !== 'targetShare')
  return position === 'RB' || position === 'WR' || position === 'TE' ? USAGE_MEASURES : []
}

export function evidenceAllowedMeasures(position: string | null, market: string) {
  const receiving = ['receptions', 'receiving_yards', 'receiving_targets'].includes(market)
  if (receiving && (position === 'RB' || position === 'WR' || position === 'TE')) {
    const prefix = position.toLowerCase()
    return POSITION_ALLOWED_ROWS.filter(row => row.key === `${prefix}Receptions` || row.key === `${prefix}RecYards`)
  }
  if (position === 'RB' && (market === 'rushing_yards' || market === 'rushing_attempts')) {
    return POSITION_ALLOWED_ROWS.filter(row => row.key === 'rbCarries' || row.key === 'rbRushYards')
  }
  return []
}

export function evidenceContextGameId(game: ContextGame | null, row: ContextLine): number | null {
  if (!game || !Number.isSafeInteger(game.gameId) || game.gameId <= 0 || !evidenceUsageMeasures(row.position).length) return null
  return game.lines.some(line => line.lineId === row.lineId && line.playerId === row.playerId && line.market === row.market)
    ? game.gameId : null
}

export function selectedEvidenceContext(
  data: NflGameContext | undefined, game: ContextGame | null, row: ContextLine,
): { player: NflContextPlayer, opponent: NflMatchupTeam } | null {
  if (!data || !game || data.gameId !== evidenceContextGameId(game, row)) return null
  if (data.matchupContext.away.team !== game.awayTeam || data.matchupContext.home.team !== game.homeTeam) return null
  const players = data.players.filter(player => player.playerId === row.playerId)
  if (players.length !== 1 || players[0].position !== row.position) return null
  const player = players[0]
  const { away, home } = data.matchupContext
  if (player.team === away.team) return { player, opponent: home }
  if (player.team === home.team) return { player, opponent: away }
  return null
}
