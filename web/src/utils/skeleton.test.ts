import { describe, expect, it } from 'vitest'
import { SKELETON_MAX_WIDTH, SKELETON_MIN_WIDTH, skeletonWidths } from './skeleton'

describe('skeletonWidths', () => {
  it('returns one width per row and column', () => {
    const widths = skeletonWidths(8, 5)
    expect(widths).toHaveLength(8)
    expect(widths.every(row => row.length === 5)).toBe(true)
  })

  it('gives the same widths for the same request', () => {
    expect(skeletonWidths(6, 4)).toEqual(skeletonWidths(6, 4))
  })

  it('keeps every width inside its bounds', () => {
    const all = skeletonWidths(20, 9).flat()
    expect(Math.min(...all)).toBeGreaterThanOrEqual(SKELETON_MIN_WIDTH)
    expect(Math.max(...all)).toBeLessThanOrEqual(SKELETON_MAX_WIDTH)
  })

  it('varies widths between rows', () => {
    const firstColumn = skeletonWidths(8, 3).map(row => row[0])
    expect(new Set(firstColumn).size).toBeGreaterThan(4)
  })

  it('returns no bars for zero or negative sizes', () => {
    expect(skeletonWidths(0, 4)).toEqual([])
    expect(skeletonWidths(4, 0)).toEqual([])
    expect(skeletonWidths(-1, 3)).toEqual([])
  })
})
