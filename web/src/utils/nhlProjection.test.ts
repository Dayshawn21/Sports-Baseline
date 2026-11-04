import { expect, it } from 'vitest'
import type { NhlProjection, NhlProjectionFlag } from '~/types/nhl'
import { NHL_PROJECTION_CAPTION, nhlGapLabel, nhlProjectionNote, nhlProjectionValue } from '~/utils/nhlProjection'

const ALL_FLAGS: NhlProjectionFlag[] = [
  'few_prior_games', 'low_toi', 'not_center', 'no_goalie_report', 'starter_unconfirmed',
  'other_starter_expected', 'context_stale', 'injured_out', 'injury_listed', 'injury_context_stale',
]

function projection(overrides: Partial<NhlProjection> = {}): NhlProjection {
  return { modelVersion: 'nhl-reference-v1', value: 3, gamesInSample: 20, gap: 0.5, flags: [], ...overrides }
}

it('shows one decimal, a dash for no number, and keeps a real zero', () => {
  expect(nhlProjectionValue(projection({ value: 24.8 }))).toBe('24.8')
  expect(nhlProjectionValue(projection({ value: 0 }))).toBe('0.0')
  expect(nhlProjectionValue(projection({ value: null }))).toBe('-')
})

it('signs the gap, shows zero unsigned and dashes a missing gap', () => {
  expect(nhlGapLabel(0.5)).toBe('+0.5')
  expect(nhlGapLabel(-1.05)).toBe('-1.1')
  expect(nhlGapLabel(0)).toBe('0.0')
  expect(nhlGapLabel(-0.04)).toBe('0.0')
  expect(nhlGapLabel(null)).toBe('-')
})

it('has a reason for every flag, joins several, and stays silent with none', () => {
  for (const flag of ALL_FLAGS) expect(nhlProjectionNote(projection({ flags: [flag] }))).toBeTruthy()
  expect(nhlProjectionNote(projection({ flags: ['injury_listed', 'injury_context_stale'] })))
    .toBe('Injury listed · Injury report is stale')
  expect(nhlProjectionNote(projection())).toBeNull()
  expect(nhlProjectionNote(projection({ value: null, gap: null, flags: ['starter_unconfirmed'] }))).toBe('Starter not confirmed')
})

it('never uses pick language in the caption or any reason', () => {
  const texts = [NHL_PROJECTION_CAPTION.replace('not a pick', ''), ...ALL_FLAGS.map(flag => nhlProjectionNote(projection({ flags: [flag] })) ?? '')]
  for (const text of texts) expect(text).not.toMatch(/\b(pick|bet|edge|value|lock|play)\b/i)
  expect(NHL_PROJECTION_CAPTION).toContain('not a pick')
})
