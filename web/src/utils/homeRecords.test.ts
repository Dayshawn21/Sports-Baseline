import { describe, expect, it } from 'vitest'
import type { ModelPredictionsResponse } from '~/types/tennis'
import { rankingRecord, tennisRecord } from '~/utils/homeRecords'

const slices = (...verdicts: string[]) => ({ slices: verdicts.map(verdict => ({ verdict })) })

describe('rankingRecord', () => {
  it('reads Accruing while no slice has adopted, whatever else the verdicts say', () => {
    expect(rankingRecord('nfl', slices('insufficient', 'insufficient', 'reject', 'pass'), 'ready'))
      .toEqual({ sport: 'nfl', status: 'ready', label: 'Accruing', detail: 'V4 forward ranking check' })
  })

  it('counts adopted slices against the total', () => {
    expect(rankingRecord('nba', slices('adopt', 'insufficient', 'adopt', 'reject'), 'ready').label).toBe('2 of 4 adopted')
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

  it('reads the pooled ensemble-versus-market verdict', () => {
    const group = (signal: string) => [{ group: 'ATP+WTA', n: 500, components: [{ name: 'ensemble', vsMarket: { signal } }] }]
    expect(tennisRecord(response(group('positive')), 'ready').label).toBe('Ahead')
    expect(tennisRecord(response(group('neutral')), 'ready').label).toBe('Not ahead')
  })

  it('has a placeholder before its data arrives', () => {
    expect(tennisRecord(undefined, 'loading')).toMatchObject({ sport: 'tennis', status: 'loading', label: '--' })
  })
})
