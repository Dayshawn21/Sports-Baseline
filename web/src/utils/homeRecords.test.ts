import { describe, expect, it } from 'vitest'
import type { ModelPredictionsResponse } from '~/types/tennis'
import { rankingRecord, tennisRecord } from '~/utils/homeRecords'

const slices = (...verdicts: string[]) => ({ slices: verdicts.map(verdict => ({ verdict })) })

describe('rankingRecord', () => {
  it('counts adopted slices and says nothing is adopted when none is', () => {
    expect(rankingRecord('nba', slices('insufficient', 'insufficient', 'insufficient', 'insufficient'), 'ready'))
      .toEqual({ sport: 'nba', status: 'ready', label: '0 of 4 adopted', detail: 'Forward ranking check · 4 accruing' })
  })

  it('never reads a rejected slice as still accruing: the real NFL mix names both', () => {
    expect(rankingRecord('nfl', slices('insufficient', 'reject', 'insufficient', 'reject'), 'ready'))
      .toEqual({ sport: 'nfl', status: 'ready', label: '0 of 4 adopted', detail: 'V4 forward ranking check · 2 rejected · 2 accruing' })
  })

  it('counts adopted slices against the total and names passes, leaving zero counts out', () => {
    const record = rankingRecord('nfl', slices('adopt', 'pass', 'reject', 'accruing'), 'ready')
    expect(record.label).toBe('1 of 4 adopted')
    expect(record.detail).toBe('V4 forward ranking check · 1 rejected · 1 passed · 1 accruing')
    expect(rankingRecord('nba', slices('adopt', 'adopt'), 'ready').detail).toBe('Forward ranking check')
  })

  it('shows a dash while loading and says Unavailable on error, never a made-up value', () => {
    expect(rankingRecord('nfl', undefined, 'loading')).toMatchObject({ status: 'loading', label: '--' })
    expect(rankingRecord('nba', undefined, 'error')).toMatchObject({ status: 'error', label: 'Unavailable' })
  })
})

describe('tennisRecord', () => {
  const response = (groups: unknown): ModelPredictionsResponse => ({ groups }) as ModelPredictionsResponse

  it('reads No data when the pooled ATP+WTA group is missing or empty', () => {
    expect(tennisRecord(response([]), 'ready').label).toBe('No data')
    expect(tennisRecord(response([{ group: 'ATP+WTA', n: 0, components: [] }]), 'ready').label).toBe('No data')
  })

  it('calls a tie a tie instead of "Not ahead"', () => {
    const group = (signal: string) => [{ group: 'ATP+WTA', n: 500, components: [{ name: 'ensemble', vsMarket: { signal } }] }]
    expect(tennisRecord(response(group('positive')), 'ready').label).toBe('Ahead of market')
    expect(tennisRecord(response(group('neutral')), 'ready').label).toBe('Level with market')
    expect(tennisRecord(response(group('negative')), 'ready').label).toBe('Behind market')
  })

  it('reads No data when the ensemble has no market comparison', () => {
    expect(tennisRecord(response([{ group: 'ATP+WTA', n: 500, components: [{ name: 'ensemble' }] }]), 'ready').label).toBe('No data')
  })

  it('has a placeholder before its data arrives', () => {
    expect(tennisRecord(undefined, 'loading')).toMatchObject({ sport: 'tennis', status: 'loading', label: '--' })
  })
})
