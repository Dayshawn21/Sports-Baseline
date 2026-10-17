import { describe, expect, it } from 'vitest'
import { filterNflSlateLinesByPosition, groupNflSlateLinesByPosition } from './nflPositions'

const lines = [
  { id: 1, position: 'WR' }, { id: 2, position: 'QB' }, { id: 3, position: 'WR' }, { id: 4, position: null },
]

describe('NFL position board helpers', () => {
  it('filters without changing the source order', () => {
    expect(filterNflSlateLinesByPosition(lines, 'WR').map(line => line.id)).toEqual([1, 3])
    expect(filterNflSlateLinesByPosition(lines, 'all').map(line => line.id)).toEqual([1, 2, 3, 4])
  })

  it('groups known positions and retains unknown positions as Other', () => {
    expect(groupNflSlateLinesByPosition(lines)).toEqual([
      { position: 'QB', lines: [lines[1]] },
      { position: 'WR', lines: [lines[0], lines[2]] },
      { position: 'Other', lines: [lines[3]] },
    ])
  })
})
