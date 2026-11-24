import { describe, expect, it } from 'vitest'
import { FIRST_ROW_BATCH, NEXT_ROW_BATCH, nextBatchCount, rowBatchLimit, splitRowLimit } from '~/utils/rowBatches'

describe('rowBatchLimit', () => {
  it('shows the first batch before any follow-up lands', () => {
    expect(rowBatchLimit(119, 0)).toBe(FIRST_ROW_BATCH)
  })

  it('adds one batch per follow-up and stops at the total', () => {
    expect(rowBatchLimit(119, 1)).toBe(FIRST_ROW_BATCH + NEXT_ROW_BATCH)
    expect(rowBatchLimit(119, 3)).toBe(100)
    expect(rowBatchLimit(119, 4)).toBe(119)
    expect(rowBatchLimit(119, 40)).toBe(119)
  })

  it('shows every row of a market smaller than the first batch', () => {
    expect(rowBatchLimit(12, 0)).toBe(12)
    expect(rowBatchLimit(0, 0)).toBe(0)
  })

  it('treats a negative batch count as none', () => {
    expect(rowBatchLimit(119, -2)).toBe(FIRST_ROW_BATCH)
  })

  it('honors custom sizes', () => {
    expect(rowBatchLimit(50, 2, 10, 5)).toBe(20)
  })
})

describe('nextBatchCount', () => {
  it('adds one batch on a visible page', () => {
    expect(nextBatchCount(2, false)).toBe(3)
  })

  it('takes every remaining row on a hidden page', () => {
    expect(rowBatchLimit(119, nextBatchCount(0, true))).toBe(119)
  })
})

describe('splitRowLimit', () => {
  it('fills the first table before the second', () => {
    expect(splitRowLimit(25, 90)).toEqual([25, 0])
    expect(splitRowLimit(100, 90)).toEqual([90, 10])
  })

  it('gives the second table everything when the first is empty', () => {
    expect(splitRowLimit(25, 0)).toEqual([0, 25])
  })
})
