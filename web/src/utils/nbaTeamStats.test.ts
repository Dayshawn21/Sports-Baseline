import { describe, expect, it } from 'vitest'
import type { NbaTeamSeasonStats, NbaTeamStatRate, NbaTeamStatsContext } from '~/types/nba'
import { NBA_TEAM_STATS, nbaOpponentContext, nbaTeamRateText } from '~/utils/nbaTeamStats'

function rate(overrides: Partial<NbaTeamStatRate> = {}): NbaTeamStatRate {
  return { perGame: 25.4, rank: 8, games: 10, rankedTeams: 30, ...overrides }
}

describe('team-stat presentation', () => {
  it('keeps the five API keys in table order', () => {
    expect(NBA_TEAM_STATS.map(stat => stat.key)).toEqual(['points', 'rebounds', 'assists', 'threes_made', 'blocks'])
  })
  it('formats observed rates with their actual rank population and coverage', () => {
    expect(nbaTeamRateText(rate(), 10)).toEqual({
      value: '25.4', rank: 'Rank 8 of 30', sample: '10 of 10 games', notes: [],
    })
  })
  it('shows true zero as a value and supports tied rank 1 with fewer ranked teams', () => {
    expect(nbaTeamRateText(rate({ perGame: 0, rank: 1, rankedTeams: 2 }), 10)).toMatchObject({ value: '0.0', rank: 'Rank 1 of 2' })
  })
  it('does not turn unavailable values into zero or give them a rank', () => {
    expect(nbaTeamRateText(rate({ perGame: null, rank: null, games: 0 }), 0)).toEqual({
      value: '--', rank: 'Unranked', sample: '0 of 0 games', notes: [],
    })
  })
  it('flags missing box coverage separately from small samples', () => {
    expect(nbaTeamRateText(rate({ games: 8 }), 10).notes).toEqual(['Partial coverage'])
    expect(nbaTeamRateText(rate({ games: 2 }), 10).notes).toEqual(['Partial coverage', 'Small sample'])
    expect(nbaTeamRateText(rate({ games: 1 }), 1).notes).toEqual(['Small sample'])
    expect(nbaTeamRateText(rate({ games: 3 }), 3).notes).toEqual([])
  })
  it('keeps entirely missing boxes distinct from no completed games', () => {
    expect(nbaTeamRateText(rate({ perGame: null, rank: null, games: 0 }), 5)).toEqual({
      value: '--', rank: 'Unranked', sample: '0 of 5 games', notes: ['Partial coverage'],
    })
  })
})

function context(): NbaTeamStatsContext {
  const side = (team: string, allowed: number): NbaTeamSeasonStats => ({
    team, completedGames: 10,
    stats: Object.fromEntries(NBA_TEAM_STATS.map(({ key }, index) => [key, {
      for: rate({ perGame: 99 }), allowed: rate({ perGame: allowed + index, games: 2 }),
    }])) as NbaTeamSeasonStats['stats'],
  })
  return { season: 2026, beforeDate: '2026-11-01', basis: 'stored_player_box_scores',
    away: side('NY', 10), home: side('BOS', 20) }
}

describe('opponent team context', () => {
  it.each(NBA_TEAM_STATS)('selects the opponent allowed $key, never its for value', ({ key, label }) => {
    const input = context()
    expect(nbaOpponentContext(input, 'NY', key)).toEqual({
      kind: 'matched', opponent: 'BOS', measure: label.toLowerCase(), rate: input.home.stats[key].allowed,
      completedGames: 10, season: 2026, beforeDate: '2026-11-01',
    })
  })
  it('reverses the opponent when the row belongs to the home team', () => {
    expect(nbaOpponentContext(context(), 'BOS', 'assists')).toMatchObject({
      kind: 'matched', opponent: 'NY', rate: { perGame: 12, games: 2 },
    })
  })
  it.each([null, 'LAL', 'NYK', ''])('never guesses from a missing, foreign or unnormalized line team %s', team => {
    expect(nbaOpponentContext(context(), team, 'points')).toMatchObject({ kind: 'unavailable', message: expect.stringContaining('line team') })
  })
  it('rejects an ambiguous pair of game sides', () => {
    const input = context()
    input.home.team = input.away.team
    expect(nbaOpponentContext(input, 'NY', 'points').kind).toBe('unavailable')
  })
  it.each(['points_rebounds', 'points_assists', 'rebounds_assists', 'points_rebounds_assists', 'double_double', 'unknown'])(
    'explains unsupported market %s without deriving a total or rank', market => {
      expect(nbaOpponentContext(context(), 'NY', market)).toEqual({
        kind: 'unavailable', message: 'Team allowed stats are not available for this market.',
      })
    },
  )
  it.each([null, undefined])('handles missing context', input => {
    expect(nbaOpponentContext(input, 'NY', 'points')).toEqual({ kind: 'unavailable', message: 'Team stats unavailable.' })
  })
  it.each([null, 0])('preserves the selected nullable rate %s without substituting another stat or team', perGame => {
    const input = context()
    input.home.stats.blocks.allowed = rate({ perGame, rank: perGame === null ? null : 1, games: perGame === null ? 0 : 1 })
    expect(nbaOpponentContext(input, 'NY', 'blocks')).toMatchObject({
      kind: 'matched', rate: { perGame, games: perGame === null ? 0 : 1 }, completedGames: 10,
    })
  })
})
