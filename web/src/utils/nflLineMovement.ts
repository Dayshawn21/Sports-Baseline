import type { LineMovementHistory } from '~/types/lineMovement'
import { chartScale, project, type ChartScale } from '~/utils/matchOdds'

/** Keeps a line that barely moves from filling the plot and reading as a big swing. */
const MIN_SPAN_POINTS = 3

export interface NflLineChart {
  scale: ChartScale
  /** Step vertices as 0-1 plot fractions: the line holds each value until the next move. */
  points: Array<{ x: number, y: number }>
  open: number
  current: number
  /** Current minus open, rounded to the half point books use; 0 when it never moved. */
  move: number
}

/**
 * The chart runs to kickoff, or to now when kickoff is still ahead, so the last line
 * extends across the time it has stood rather than stopping at its fetch.
 */
export function lineMovementChart(history: LineMovementHistory, startUtc: string | null, now: Date): NflLineChart | null {
  const steps = history.steps
  if (steps.length === 0) return null
  const last = Date.parse(steps[steps.length - 1].fetchedAt)
  const kickoff = startUtc === null ? Number.NaN : Date.parse(startUtc)
  const end = Math.max(last, Number.isNaN(kickoff) ? now.getTime() : Math.min(kickoff, now.getTime()))
  const endAt = new Date(end).toISOString()
  const vertices = steps.flatMap((step, index) => index === 0
    ? [{ at: step.fetchedAt, value: step.line }]
    : [{ at: step.fetchedAt, value: steps[index - 1].line }, { at: step.fetchedAt, value: step.line }])
  vertices.push({ at: endAt, value: steps[steps.length - 1].line })
  const scale = chartScale([{ book: history.book, points: vertices }], [], MIN_SPAN_POINTS)
  if (scale === null) return null
  const open = steps[0].line
  const current = steps[steps.length - 1].line
  return {
    scale,
    points: vertices.map(vertex => project(scale, vertex.at, vertex.value)),
    open,
    current,
    move: Math.round((current - open) * 2) / 2,
  }
}
