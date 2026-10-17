import { describe, expect, it } from 'vitest'
import { groupNflPropRows } from '~/utils/nflPropRows'

const line = (lineId: number, oddsType: string | null, value: number, fetchedAt = '2026-09-18T12:00:00Z') => ({
  lineId,
  playerId: 12,
  market: 'pass_attempts',
  segment: 'full_game',
  oddsType,
  line: value,
  fetchedAt,
})

describe('groupNflPropRows', () => {
  it('uses the newest standard line and retains unique alternate lines', () => {
    const rows = groupNflPropRows([
      line(1, 'standard', 30.5, '2026-09-18T10:00:00Z'),
      line(2, 'standard', 31.5),
      line(3, 'goblin', 27.5),
      line(4, 'demon', 34.5),
      line(5, 'goblin', 27.5, '2026-09-18T13:00:00Z'),
    ])

    expect(rows).toHaveLength(1)
    expect(rows[0].primary.lineId).toBe(2)
    expect(rows[0].alternates.map(item => item.lineId)).toEqual([5, 4])
  })

  it('falls back to the newest line when the provider has no standard line', () => {
    const rows = groupNflPropRows([line(1, 'goblin', 25.5), line(2, 'demon', 33.5, '2026-09-18T14:00:00Z')])

    expect(rows[0].primary.lineId).toBe(2)
    expect(rows[0].alternates.map(item => item.lineId)).toEqual([1])
  })

  it('keeps different markets and players separate', () => {
    const rows = groupNflPropRows([
      line(1, 'standard', 30.5),
      { ...line(2, 'standard', 250.5), market: 'passing_yards' },
      { ...line(3, 'standard', 30.5), playerId: 99 },
    ])

    expect(rows).toHaveLength(3)
  })
})
