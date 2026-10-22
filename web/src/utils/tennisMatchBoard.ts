import type { MatchBestPicks, MatchDetail, PropLine } from '~/types/tennis'
import { buildTennisPropBoard, type TennisPropSource } from '~/utils/tennisPropBoard'
import { isFinished } from '~/utils/tennisMatch'
import { anglePicks, bestBetPicks, composeUnifiedMatches } from '~/utils/unifiedTennis'

export function canLoadMatchPicks(detail: MatchDetail): boolean {
  return !isFinished(detail) && detail.startUtc != null
}

export function matchPickGroups(detail: MatchDetail, matches: MatchBestPicks[]) {
  const bestMatch = matches.find(match => match.matchId === detail.matchId)
  const match = composeUnifiedMatches([], canLoadMatchPicks(detail) && bestMatch
    ? [{ ...bestMatch, picks: bestMatch.picks.filter(pick => pick.pickType !== 'prop') }] : [], [],
  { showLeans: true, upcomingOnly: false, sort: 'opportunity' })[0]
  return { bestBets: match ? bestBetPicks(match) : [], angles: match ? anglePicks(match) : [] }
}

export function matchPropCategories(
  props: PropLine[], detail: MatchDetail, source: TennisPropSource, playerId: number | null,
) {
  const player = [detail.p1, detail.p2].find(item => item.playerId === playerId)
  const lines = props.filter(line => line.matchId === detail.matchId && (playerId == null ||
    (player != null && (line.playerId != null ? line.playerId === player.playerId
      : line.playerName?.trim().toLowerCase() === player.name.trim().toLowerCase()))))
  return buildTennisPropBoard(lines, detail.prediction ? [detail.prediction] : [], source, 'all', true)
}
