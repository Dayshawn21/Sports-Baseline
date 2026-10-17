import { describe, expect, it } from 'vitest'
import { filterNflSlateLinesByPeriod } from '~/utils/nflPropPeriods'

const lines = [
  { lineId: 1, segment: 'full_game' },
  { lineId: 2, segment: 'first_half' },
  { lineId: 3, segment: 'q1' },
  { lineId: 4, segment: 'season' },
  { lineId: 5, segment: 'second_half' },
]

describe('filterNflSlateLinesByPeriod', () => {
  it.each([
    ['full_game', [1]],
    ['first_half', [2]],
    ['q1', [3]],
  ] as const)('keeps only %s lines', (period, expectedLineIds) => {
    expect(filterNflSlateLinesByPeriod(lines, period).map(line => line.lineId)).toEqual(expectedLineIds)
  })
})
