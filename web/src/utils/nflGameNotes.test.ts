import { describe, expect, it } from 'vitest'
import type { NflNoteInjury } from '~/types/nfl'
import { TEAM_STAT_ROWS, formLabel, gamesLabel, injuriesByTeam, injuryGroups, rankLabel, restLabel, statValue } from './nflGameNotes'

describe('injuryGroups', () => {
  const injury = (position: string, playerId: number): NflNoteInjury => ({
    playerId, playerName: `Player ${playerId}`, team: 'NE', position, injuryStatus: 'Out', practiceStatus: null, injury: 'Knee',
  })

  it('separates skill, offensive line, defensive and other positions without dropping anyone', () => {
    const rows = ['CB', 'OT', 'QB', 'G', 'C', 'DE', 'DT', 'LB', 'SAF', 'K', 'UNK', 'fb', 'EDGE'].map(injury)
    const groups = injuryGroups(rows)
    expect(groups.map(group => [group.label, group.rows.map(row => row.position)])).toEqual([
      ['Offensive skill positions', ['QB', 'fb']], ['Offensive line', ['OT', 'G', 'C']],
      ['Defense', ['CB', 'DE', 'DT', 'LB', 'SAF', 'EDGE']], ['Special teams / other', ['K', 'UNK']],
    ])
    expect(groups.flatMap(group => group.rows)).toHaveLength(rows.length)
  })

  it('omits empty groups and preserves incoming severity order within each group', () => {
    const rows = [injury('CB', 1), injury('LB', 2)]
    expect(injuryGroups(rows)).toEqual([{ label: 'Defense', rows }])
    expect(injuryGroups([])).toEqual([])
  })
})

describe('formLabel', () => {
  it('puts the team score first and marks home and away', () => {
    expect(formLabel({ week: 2, opponent: 'CAR', isHome: true, pointsFor: 3, pointsAgainst: 34, result: 'L' })).toBe('L 3-34 vs CAR')
    expect(formLabel({ week: 2, opponent: 'NYJ', isHome: false, pointsFor: 20, pointsAgainst: 17, result: 'W' })).toBe('W 20-17 @ NYJ')
  })
})

describe('restLabel', () => {
  it('flags a short week and shows nothing when rest is unknown', () => {
    expect(restLabel({ restDays: 4, shortWeek: true })).toBe('Short week · 4 days rest')
    expect(restLabel({ restDays: 10, shortWeek: false })).toBe('10 days rest')
    expect(restLabel({ restDays: null, shortWeek: false })).toBeNull()
  })
})

describe('injuriesByTeam', () => {
  it('groups away then home and keeps each team in API order', () => {
    const injury = (playerName: string, team: string): NflNoteInjury => ({
      playerId: 1, playerName, team, position: 'WR', injuryStatus: 'Out', practiceStatus: null, injury: null,
    })
    const grouped = injuriesByTeam([injury('A', 'GB'), injury('B', 'ATL'), injury('C', 'GB')], 'ATL', 'GB')

    expect(grouped.map(([team, rows]) => [team, rows.map(row => row.playerName)])).toEqual([['ATL', ['B']], ['GB', ['A', 'C']]])
  })

  it('keeps an empty team so the panel can say none reported', () => {
    expect(injuriesByTeam([], 'ATL', 'GB')).toEqual([['ATL', []], ['GB', []]])
  })
})

describe('statValue', () => {
  it('shows per-game stats to one decimal', () => {
    expect(statValue({ value: 24.5, rank: 8 }, 'perGame')).toBe('24.5')
    expect(statValue({ value: 212, rank: 1 }, 'perGame')).toBe('212.0')
  })

  it('signs EPA per play to two decimals', () => {
    expect(statValue({ value: 0.14, rank: 7 }, 'epa')).toBe('+0.14')
    expect(statValue({ value: -0.05, rank: 20 }, 'epa')).toBe('-0.05')
    expect(statValue({ value: 0, rank: 16 }, 'epa')).toBe('0.00')
  })

  it('shows success rate as a whole percent', () => {
    expect(statValue({ value: 0.43, rank: 17 }, 'rate')).toBe('43%')
  })

  it('shows a dash for a stat that is not loaded, never zero', () => {
    expect(statValue({ value: null, rank: null }, 'perGame')).toBe('-')
    expect(statValue({ value: null, rank: null }, 'epa')).toBe('-')
  })
})

describe('rankLabel', () => {
  it('uses ordinal suffixes, with 11th to 13th as the exception', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 32].map(rankLabel)).toEqual(
      ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '23rd', '32nd'],
    )
  })

  it('is empty when unranked', () => {
    expect(rankLabel(null)).toBe('')
  })
})

describe('gamesLabel', () => {
  it('counts games, singular for one, null before any', () => {
    expect(gamesLabel({ games: 2 })).toBe('2 games')
    expect(gamesLabel({ games: 1 })).toBe('1 game')
    expect(gamesLabel({ games: 0 })).toBeNull()
  })
})

describe('TEAM_STAT_ROWS', () => {
  it('pairs every offense stat with its allowed counterpart', () => {
    expect(TEAM_STAT_ROWS.every(row => row.defense === `${row.offense}Allowed`)).toBe(true)
  })
})
