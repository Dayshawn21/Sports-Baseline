import { expect, it } from 'vitest'
import type { NhlProjection, NhlProjectionFlag } from '~/types/nhl'
import {
  NHL_PROBABILITY_CAPTION, NHL_PROJECTION_CAPTION, nhlCoversProbability, nhlGapLabel, nhlLineProbabilityNote, nhlPercentLabel, nhlProbabilityNote,
  nhlProjectionNote, nhlProjectionValue,
} from '~/utils/nhlProjection'

const ALL_FLAGS: NhlProjectionFlag[] = [
  'few_prior_games', 'low_toi', 'not_center', 'no_goalie_report', 'starter_unconfirmed',
  'other_starter_expected', 'context_stale', 'injured_out', 'injury_listed', 'injury_context_stale',
  'integer_line', 'no_over_probability',
]

function projection(overrides: Partial<NhlProjection> = {}): NhlProjection {
  return { modelVersion: 'nhl-reference-v1', value: 3, gamesInSample: 20, gap: 0.5, pOver: null, flags: [], ...overrides }
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
  for (const flag of ALL_FLAGS.filter(flag => flag !== 'integer_line' && flag !== 'no_over_probability')) {
    expect(nhlProjectionNote(projection({ flags: [flag] }))).toBeTruthy()
  }
  expect(nhlProjectionNote(projection({ flags: ['injury_listed', 'injury_context_stale'] })))
    .toBe('Injury listed · Injury report is stale')
  expect(nhlProjectionNote(projection())).toBeNull()
  expect(nhlProjectionNote(projection({ value: null, gap: null, flags: ['starter_unconfirmed'] }))).toBe('Starter not confirmed')
})

it('never uses pick language in the caption or any reason', () => {
  const texts = [NHL_PROJECTION_CAPTION.replace('not a pick', ''), ...ALL_FLAGS.map(flag => nhlProjectionNote(projection({ flags: [flag] })) ?? nhlLineProbabilityNote([flag]) ?? '')]
  for (const text of texts) expect(text).not.toMatch(/\b(pick|bet|edge|value|lock|play)\b/i)
  expect(NHL_PROJECTION_CAPTION).toContain('not a pick')
})

it('rounds a probability to a whole percent and never prints a rare result as zero or certain', () => {
  expect(nhlPercentLabel(0.5149)).toBe('51%')
  expect(nhlPercentLabel(0.1851)).toBe('19%')
  expect(nhlPercentLabel(0.004)).toBe('<1%')
  expect(nhlPercentLabel(0)).toBe('<1%')
  expect(nhlPercentLabel(0.996)).toBe('>99%')
  expect(nhlPercentLabel(1)).toBe('>99%')
  expect(nhlPercentLabel(null)).toBe('--')
})

it('covers a market only when it has a probability or says why it has none', () => {
  expect(nhlCoversProbability(projection({ pOver: 0.4 }))).toBe(true)
  expect(nhlCoversProbability(projection({ flags: ['integer_line'] }))).toBe(true)
  expect(nhlCoversProbability(projection({ flags: ['no_over_probability'] }))).toBe(true)
  expect(nhlCoversProbability(projection())).toBe(false)
  expect(nhlCoversProbability(projection({ value: null, gap: null, flags: ['starter_unconfirmed'] }))).toBe(false)
})

it('qualifies only the two markets that tied the plain estimate, without pick language', () => {
  expect(nhlProbabilityNote('time_on_ice')).toBe(nhlProbabilityNote('goals_allowed'))
  expect(nhlProbabilityNote('goals_allowed')).toMatch(/no better than a plain normal estimate/)
  expect(nhlProbabilityNote('shots_on_goal')).toBeNull()
  expect(nhlProbabilityNote('faceoffs_won')).toBeNull()
  const texts = [NHL_PROBABILITY_CAPTION.replace('not a pick', ''), nhlProbabilityNote('time_on_ice') ?? '']
  for (const text of texts) expect(text).not.toMatch(/\b(pick|bet|edge|value|lock|play)\b/i)
  expect(NHL_PROBABILITY_CAPTION).toContain('not a pick')
})

it('keeps the per-line flags out of the projection note and in the line note', () => {
  expect(nhlProjectionNote(projection({ flags: ['integer_line'] }))).toBeNull()
  expect(nhlProjectionNote(projection({ flags: ['injury_listed', 'integer_line'] }))).toBe('Injury listed')
  expect(nhlLineProbabilityNote(['integer_line'])).toBe('Whole-number line: no P(over)')
  expect(nhlLineProbabilityNote(['injury_listed'])).toBeNull()
  expect(nhlLineProbabilityNote([])).toBeNull()
})
