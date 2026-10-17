import { describe, expect, it } from 'vitest'
import type { NflLineHistory } from '~/types/nfl'
import { lineMovementChart } from '~/utils/nflLineMovement'

const KICKOFF = '2026-09-27T17:00:00Z'
const AFTER = new Date('2026-09-28T00:00:00Z')

function history(steps: Array<[string, number]>): NflLineHistory {
  return { market: 'spread', book: 'draftkings', steps: steps.map(([fetchedAt, line]) => ({ fetchedAt, line })) }
}

describe('lineMovementChart', () => {
  it('draws steps that hold each line until the next move, out to kickoff', () => {
    const chart = lineMovementChart(history([['2026-09-18T17:00:00Z', -5.5], ['2026-09-22T17:00:00Z', -3.0]]), KICKOFF, AFTER)
    expect(chart?.points.map(point => point.x)).toEqual([0, 4 / 9, 4 / 9, 1])
    const [first, held, moved, last] = chart?.points ?? []
    expect(held.y).toBe(first.y)
    expect(moved.y).toBe(last.y)
    expect(moved.y).toBeLessThan(held.y)
    expect([chart?.open, chart?.current, chart?.move]).toEqual([-5.5, -3.0, 2.5])
  })

  it('runs to now while kickoff is still ahead', () => {
    const now = new Date('2026-09-20T17:00:00Z')
    const chart = lineMovementChart(history([['2026-09-18T17:00:00Z', 44.5]]), KICKOFF, now)
    expect(chart?.scale.tMax).toBe(now.getTime())
  })

  it('draws a single line flat across the plot and pads its range', () => {
    const chart = lineMovementChart(history([['2026-09-18T17:00:00Z', 44.5]]), KICKOFF, AFTER)
    expect(chart?.points.map(point => point.y)).toEqual([0.5, 0.5])
    expect(chart?.move).toBe(0)
    expect((chart?.scale.vMax ?? 0) - (chart?.scale.vMin ?? 0)).toBe(3)
  })

  it('never ends before the last fetch when kickoff is unknown', () => {
    const chart = lineMovementChart(history([['2026-09-18T17:00:00Z', 1.5]]), null, new Date('2026-09-18T12:00:00Z'))
    expect(chart?.scale.tMax).toBe(Date.parse('2026-09-18T17:00:00Z'))
  })

  it('is null without steps', () => {
    expect(lineMovementChart(history([]), KICKOFF, AFTER)).toBeNull()
  })
})
