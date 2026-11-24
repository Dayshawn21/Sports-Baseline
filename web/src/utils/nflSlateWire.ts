import type { NflHistorySample, NflSlateLine, NflSlateResponse, NflSlateWire, NflSlateWireLine } from '~/types/nfl'

/**
 * The API writes each history sample once and points lines at it by index
 * (`app/core/nfl_slate_wire.py`), which halved a 25 MB week. This puts the
 * samples back so everything past the transport reads the full slate shape.
 * A copy stored before the change has no `samples` and passes through.
 */
export function expandNflSlate(raw: NflSlateWire | NflSlateResponse): NflSlateResponse {
  if (!('samples' in raw)) return raw
  const { samples, games, ...rest } = raw
  const sample = (index: number): NflHistorySample => {
    const found = samples[index]
    if (found === undefined) throw new Error(`NFL slate line points at history sample ${index}, but only ${samples.length} were sent`)
    return found
  }
  const expandLine = ({ recentFormLong, ...line }: NflSlateWireLine): NflSlateLine => ({
    ...line,
    recentForm: sample(line.recentForm),
    opponentHistory: sample(line.opponentHistory),
    opponentAllowedHistory: sample(line.opponentAllowedHistory),
    ...(recentFormLong == null ? {} : { recentFormLong: sample(recentFormLong) }),
  })
  return { ...rest, games: games.map(game => ({ ...game, lines: game.lines.map(expandLine) })) }
}
