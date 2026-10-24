import { expect, it } from 'vitest'
import type { NhlLineOnlyLine } from '~/types/nhl'
import { NHL_LINE_ONLY_MARKETS, nhlLineOnlyGroups, nhlMarketLabel, nhlOddsTypeCounts, nhlPropLineLabel } from '~/utils/nhlLineOnly'

function line(overrides: Partial<NhlLineOnlyLine> = {}): NhlLineOnlyLine {
  return {
    provider: 'prizepicks', providerPropId: 'a', playerId: 7, playerName: 'Player', position: null, team: null,
    market: 'time_on_ice', oddsType: 'standard', line: 20.5, fetchedAt: '2026-10-23T12:00:00Z', ...overrides,
  }
}

it('covers all twelve market labels and sorts in the server enum order', () => {
  const source = NHL_LINE_ONLY_MARKETS.toReversed().map(market => line({ market, providerPropId: market }))
  const groups = nhlLineOnlyGroups(source)
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

it('preserves every offering with stable keys, including identical player/type/price', () => {
  const source = [line({ providerPropId: 'b' }), line(), line({ providerPropId: 'c', oddsType: 'demon' }), line({ providerPropId: 'd', oddsType: 'goblin' })]
  Object.freeze(source)
  source.forEach(Object.freeze)
  const [group] = nhlLineOnlyGroups(source)
  expect(group.rows.map(row => row.providerPropId)).toEqual(['c', 'd', 'a', 'b'])
  expect(group.rows.map(row => row.key)).toEqual(['prizepicks:c', 'prizepicks:d', 'prizepicks:a', 'prizepicks:b'])
  expect(group.rows.map(row => row.oddsTypeLabel)).toEqual(['Demon', 'Goblin', 'Standard', 'Standard'])
  expect(group.rows.every(row => row.lineLabel === '20.5 min')).toBe(true)
  expect(source[0].providerPropId).toBe('b')
  expect('key' in source[0]).toBe(false)
})

it('orders by player name, player id, odds type, line and offering id without merging players', () => {
  const source = [
    line({ providerPropId: 'z' }), line({ providerPropId: 'b', playerId: 8 }),
    line({ providerPropId: 'c', line: 19.5 }), line({ providerPropId: 'd', playerName: 'Aaron' }),
    line({ providerPropId: 'a' }),
  ]
  expect(nhlLineOnlyGroups(source)[0].rows.map(row => row.providerPropId)).toEqual(['d', 'c', 'a', 'z', 'b'])
  expect(nhlLineOnlyGroups([])).toEqual([])
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
