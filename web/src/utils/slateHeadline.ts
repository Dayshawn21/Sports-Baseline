import { type SlatePhase, slatePhase } from '~/utils/slateOrder'
import { countPart, dayClockCt, slatePeriodLine, startTimes } from '~/utils/slatePeriod'

export interface HeadlineGame {
  state: Parameters<typeof slatePhase>[0]
  startUtc: string | null
}

/**
 * What is left of a slate, under the "No picks" headline: "1 game left · Mon 7:15 PM CT",
 * "3 games left · 1 live · next Sun 7:20 PM CT", or "All games played · 1 result pending".
 */
export function slateRemainingLine(games: readonly HeadlineGame[], now: number): string {
  if (games.length === 0) return ''
  const phases: SlatePhase[] = games.map(game => slatePhase(game.state))
  const left = phases.filter(phase => phase === 'live' || phase === 'upcoming').length
  const live = phases.filter(phase => phase === 'live').length
  const pending = games.filter(game => game.state === 'pending').length
  if (left === 0) return slatePeriodLine(['All games played', pending > 0 && `${pending} result pending`])
  const upcoming = startTimes(games.filter(game => slatePhase(game.state) === 'upcoming').map(game => game.startUtc))
    .filter(start => start > now)
  const next = upcoming.length ? Math.min(...upcoming) : null
  const alone = left === 1 && live === 0
  return slatePeriodLine([
    `${countPart(left, 'game')} left`,
    live > 0 && `${live} live`,
    next !== null && `${alone ? '' : 'next '}${dayClockCt(next)}`,
  ])
}
