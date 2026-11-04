import { expect, it } from 'vitest'
import type { NhlLineOnlyLine } from '~/types/nhl'
import { NHL_LINE_ONLY_MARKETS, nhlMarketLabel, nhlOddsTypeCounts, nhlPropLineLabel, nhlPropListGroups } from '~/utils/nhlLineOnly'

function line(overrides: Partial<NhlLineOnlyLine> = {}): NhlLineOnlyLine {
  return {
    provider: 'prizepicks', providerPropId: 'a', playerId: 7, playerName: 'Player', position: null, team: null,
    market: 'time_on_ice', oddsType: 'standard', line: 20.5, fetchedAt: '2026-10-23T12:00:00Z',
    projection: { modelVersion: 'nhl-reference-v1', value: null, gamesInSample: 0, gap: null, flags: ['few_prior_games'] }, ...overrides,
  }
}

it('covers all twelve market labels and sorts in the server enum order', () => {
  const source = NHL_LINE_ONLY_MARKETS.toReversed().map(market => line({ market, providerPropId: market }))
  const groups = nhlPropListGroups(source)
  expect(groups.map(group => group.market)).toEqual(NHL_LINE_ONLY_MARKETS)
  expect(groups.map(group => group.label)).toEqual([
    'Shots on Goal', 'Points', 'Assists', 'Goals', 'Power Play Points', 'Blocked Shots',
    'Plus/Minus', 'Goalie Saves', 'Hits', 'Time On Ice', 'Goals Allowed', 'Faceoffs Won',
  ])
  expect(nhlMarketLabel('time_on_ice')).toBe('Time On Ice')
})

it('keeps provider minutes, positive/negative Plus/Minus and zero lines', () => {
  expect(nhlPropLineLabel('time_on_ice', 20.5)).toBe('20.5 min')
  expect(nhlPropLineLabel('time_on_ice', 0)).toBe('0 min')
  expect(nhlPropLineLabel('plus_minus', 0.5)).toBe('+0.5')
  expect(nhlPropLineLabel('plus_minus', -0.5)).toBe('-0.5')
  expect(nhlPropLineLabel('plus_minus', 0)).toBe('0')
  expect(nhlPropLineLabel('goals', 0)).toBe('0')
})

it('counts each odds type in Standard, Goblin, Demon order, keeping zeros', () => {
  const source = [line({ oddsType: 'demon' }), line({ oddsType: 'demon', providerPropId: 'b' }), line({ oddsType: 'standard', providerPropId: 'c' })]
  expect(nhlOddsTypeCounts(source)).toEqual([
    { oddsType: 'standard', label: 'Standard', count: 1 },
    { oddsType: 'goblin', label: 'Goblin', count: 0 },
    { oddsType: 'demon', label: 'Demon', count: 2 },
  ])
  expect(nhlOddsTypeCounts([]).map(entry => entry.count)).toEqual([0, 0, 0])
})

it('collapses the offerings of one player to one row with rungs in line order', () => {
  const source = [
    line({ providerPropId: 'a', oddsType: 'demon', line: 22.5 }),
    line({ providerPropId: 'b', oddsType: 'standard', line: 20.5 }),
    line({ providerPropId: 'c', oddsType: 'goblin', line: 18.5 }),
  ]
  const [group] = nhlPropListGroups(source)
  expect(group.rows).toHaveLength(1)
  expect(group.rows[0].rungs.map(rung => rung.label)).toEqual(['18.5 min', '20.5 min', '22.5 min'])
  expect(group.rows[0].rungs.map(rung => rung.oddsTypeLabel)).toEqual(['Goblin', 'Standard', 'Demon'])
  expect(group.rows[0].standard).toBe('20.5 min')
  expect(group.rows[0].key).toBe('time_on_ice:7')
})

it('keeps two players with the same name apart and orders rows by name then id', () => {
  const source = [
    line({ providerPropId: 'a', playerId: 9, playerName: 'Sam' }),
    line({ providerPropId: 'b', playerId: 4, playerName: 'Sam' }),
    line({ providerPropId: 'c', playerId: 6, playerName: 'Aaron' }),
  ]
  expect(nhlPropListGroups(source)[0].rows.map(row => row.playerId)).toEqual([6, 4, 9])
})

it('orders the list groups by the server market enum and returns none for no lines', () => {
  const source = NHL_LINE_ONLY_MARKETS.toReversed().map(market => line({ market, providerPropId: market }))
  expect(nhlPropListGroups(source).map(group => group.market)).toEqual(NHL_LINE_ONLY_MARKETS)
  expect(nhlPropListGroups([])).toEqual([])
})

it('signs plus/minus and writes minutes on the rungs', () => {
  const [plusMinus] = nhlPropListGroups([line({ market: 'plus_minus', line: 0.5, oddsType: 'demon' })])
  expect(plusMinus.rows[0].rungs[0].label).toBe('+0.5')
  const [toi] = nhlPropListGroups([line({ line: 20.5 })])
  expect(toi.rows[0].rungs[0].label).toBe('20.5 min')
})

it('has a null standard with no standard rung and still lists the alternates', () => {
  const [group] = nhlPropListGroups([line({ oddsType: 'goblin', line: 1.5 }), line({ providerPropId: 'b', oddsType: 'demon', line: 3.5 })])
  expect(group.rows[0].standard).toBeNull()
  expect(group.rows[0].rungs.map(rung => rung.label)).toEqual(['1.5 min', '3.5 min'])
})

it('uses the newest fetch time and shows a repeated offering once', () => {
  const [group] = nhlPropListGroups([
    line({ providerPropId: 'a', fetchedAt: '2026-10-23T12:00:00Z' }),
    line({ providerPropId: 'b', fetchedAt: '2026-10-23T15:30:00Z' }),
    line({ providerPropId: 'c', fetchedAt: '2026-10-23T09:00:00Z', oddsType: 'goblin', line: 18.5 }),
  ])
  expect(group.rows[0].fetchedAt).toBe('2026-10-23T15:30:00Z')
  expect(group.rows[0].rungs).toHaveLength(2)
})

it('does not change its input', () => {
  const source = Object.freeze([Object.freeze(line()), Object.freeze(line({ providerPropId: 'b', oddsType: 'demon', line: 22.5 }))])
  expect(() => nhlPropListGroups(source)).not.toThrow()
})

it('carries the projection and the standard line gap onto each row and rung', () => {
  const projection = { modelVersion: 'nhl-reference-v1', value: 3, gamesInSample: 20, gap: null, flags: [] as never[] }
  const [group] = nhlPropListGroups([
    line({ providerPropId: 'a', market: 'hits', line: 2.5, projection: { ...projection, gap: 0.5 } }),
    line({ providerPropId: 'b', market: 'hits', line: 3.5, oddsType: 'demon', projection: { ...projection, gap: -0.5 } }),
  ])
  const [row] = group.rows
  expect(row.standardGap).toBe(0.5)
  expect(row.projection.value).toBe(3)
  expect(row.rungs.map(rung => rung.gap)).toEqual([0.5, -0.5])
})

it('has no standard gap when the player has no standard line', () => {
  const [group] = nhlPropListGroups([line({ oddsType: 'goblin' })])
  expect(group.rows[0].standardGap).toBeNull()
})
