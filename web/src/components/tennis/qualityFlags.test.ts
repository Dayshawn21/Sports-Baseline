import { describe, expect, it } from 'vitest'
import { getDisplayFlags } from './qualityFlags'

describe('getDisplayFlags', () => {
  it('shows partial context when recent form is missing', () => {
    expect(getDisplayFlags(['ctx_last90_missing'])).toEqual(['partial_context'])
  })

  it('hides the opponent-rank gaps entirely', () => {
    expect(getDisplayFlags(['ctx_top20_missing', 'ctx_top50_missing'])).toEqual([])
  })

  it('collapses all three context flags into one chip', () => {
    expect(
      getDisplayFlags(['ctx_top20_missing', 'ctx_last90_missing', 'ctx_top50_missing']),
    ).toEqual(['partial_context'])
  })

  it('keeps other flags in order', () => {
    expect(
      getDisplayFlags(['stale_odds', 'ctx_top20_missing', 'ml_features_partial']),
    ).toEqual(['stale_odds', 'ml_features_partial'])
    expect(getDisplayFlags(['stale_odds', 'ctx_last90_missing', 'market_missing'])).toEqual([
      'partial_context',
      'stale_odds',
      'market_missing',
    ])
  })
})
