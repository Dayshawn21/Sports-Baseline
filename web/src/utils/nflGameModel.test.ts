import { describe, expect, it } from 'vitest'
import type { NflGameModel, NflGameOdds, NflQbChange } from '~/types/nfl'
import { nflGameModelSummary, qbChangeText } from './nflGameModel'

const model: NflGameModel = {
  modelVersion: 'nfl-elo-v1',
  homeElo: 1540,
  awayElo: 1500,
  homeWinProbability: 0.555,
  homeSpread: -2.3,
  total: 47,
  marketHomeWinProbability: 0.5174,
}
const odds: NflGameOdds = { book: 'draftkings', homeMoneyline: -118, awayMoneyline: -102, homeSpread: -1.5, total: 47.5 }

describe('nflGameModelSummary', () => {
  it('names the home favorite and phrases every gap by team or direction', () => {
    expect(nflGameModelSummary(model, odds, 'CHI', 'PHI')).toEqual({
      spread: { model: 'CHI -2.3', market: 'CHI -1.5', gap: '0.8 pts more on CHI' },
      winProbability: { model: 'CHI 55.5%', market: 'CHI 51.7%', gap: '3.8 pts more on CHI' },
      total: { model: '47.0', market: '47.5', gap: '0.5 under market' },
    })
  })

  it('names the away team when it is favored', () => {
    const summary = nflGameModelSummary(
      { ...model, homeSpread: 3.4, homeWinProbability: 0.38, total: 42.4 },
      { ...odds, homeSpread: 2.5, total: 40.5 },
      'CLE', 'PIT',
    )
    expect(summary?.spread).toEqual({ model: 'PIT -3.4', market: 'PIT -2.5', gap: '0.9 pts more on PIT' })
    expect(summary?.total.gap).toBe('1.9 over market')
  })

  it('shows PK for a spread within 0.05 of zero and matching values as a match', () => {
    const summary = nflGameModelSummary({ ...model, homeSpread: -0.04 }, { ...odds, homeSpread: 0, total: 47.02 }, 'CHI', 'PHI')
    expect(summary?.spread).toEqual({ model: 'PK', market: 'PK', gap: 'Matches market' })
    expect(summary?.total.gap).toBe('Matches market')
  })

  it('makes a disagreement on the favorite readable without signs', () => {
    const summary = nflGameModelSummary({ ...model, homeSpread: -1 }, { ...odds, homeSpread: 2.5 }, 'CHI', 'PHI')
    expect(summary?.spread).toEqual({ model: 'CHI -1.0', market: 'PHI -2.5', gap: '3.5 pts more on CHI' })
  })

  it('keeps the model value and drops the gap for each missing market piece', () => {
    const summary = nflGameModelSummary(
      { ...model, marketHomeWinProbability: null },
      { ...odds, homeSpread: null, total: null },
      'CHI', 'PHI',
    )
    expect(summary).toEqual({
      spread: { model: 'CHI -2.3', market: 'No market line', gap: null },
      winProbability: { model: 'CHI 55.5%', market: 'No market line', gap: null },
      total: { model: '47.0', market: 'No market line', gap: null },
    })
  })

  it('treats a game with no stored odds the same way', () => {
    const summary = nflGameModelSummary({ ...model, marketHomeWinProbability: null }, null, 'CHI', 'PHI')
    expect([summary?.spread.market, summary?.total.market]).toEqual(['No market line', 'No market line'])
  })

  it('returns null without a model line', () => {
    expect(nflGameModelSummary(null, odds, 'CHI', 'PHI')).toBeNull()
  })
})

describe('qbChangeText', () => {
  const change = (overrides: Partial<NflQbChange>): NflQbChange => ({
    team: 'TB', usualStarter: 'Baker Mayfield', reasons: [], injuryStatus: null, injuryWeek: null,
    lastGameQb: null, lastGameWeek: null, previousQb1: null, ...overrides,
  })
  const caveat = ' The model is built from past scores and does not adjust for this.'

  it('names the injury and the backup with the week each was stored', () => {
    expect(qbChangeText(change({ reasons: ['injured', 'backup_started'], injuryStatus: 'Out', injuryWeek: 4, lastGameQb: 'Jalon Daniels', lastGameWeek: 4 })))
      .toBe(`TB QB change: Baker Mayfield, the usual starter, was listed Out in week 4. Jalon Daniels led TB in passes in week 4.${caveat}`)
  })

  it('names the QB1 the usual starter replaced', () => {
    expect(qbChangeText(change({ reasons: ['depth_chart'], previousQb1: 'Teddy Bridgewater' })))
      .toBe(`TB QB change: Baker Mayfield is the usual starter. Baker Mayfield replaced Teddy Bridgewater as QB1 on the latest depth chart.${caveat}`)
  })
})
