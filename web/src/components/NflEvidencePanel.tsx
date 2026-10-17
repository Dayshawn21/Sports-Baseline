import {
  DetailBreakdown, DetailContext, DetailFlags, DetailGameLog, DetailGameMarket, DetailHeader, DetailLines, DetailProjection,
  DetailSportsbook, DetailStatus,
} from '~/components/nfl/NflPropDetailSections'
import type { NflSlateGame, NflSlateLine } from '~/types/nfl'
import { nflPropDetail } from '~/utils/nflPropDetail'

export default function NflEvidencePanel({ row, game, alternates = [], showGameLink = true, showPlayerLink = true }: { row: NflSlateLine, game: NflSlateGame | null, alternates?: NflSlateLine[], showGameLink?: boolean, showPlayerLink?: boolean }) {
  const detail = nflPropDetail(row, game, alternates, Date.now())
  return <aside className="nfl-prop-detail" aria-label={`Evidence for ${row.playerName}`}>
    <DetailHeader detail={detail} playerLink={showPlayerLink ? `/nfl/player/${row.playerId}` : null} />
    <DetailProjection detail={detail} />
    <DetailGameLog row={row} detail={detail} />
    <DetailContext detail={detail} />
    <DetailBreakdown detail={detail} />
    <DetailLines detail={detail} />
    <DetailSportsbook detail={detail} />
    <DetailGameMarket detail={detail} gameLink={showGameLink && game ? `/nfl/game/${game.gameId}` : null} />
    <DetailStatus detail={detail} />
    <DetailFlags detail={detail} />
  </aside>
}
