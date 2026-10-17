import { describe, expect, it } from 'vitest'
import type { NflLineMove, NflNoteInjury } from '~/types/nfl'
import { TEAM_STAT_ROWS, formLabel, gamesLabel, injuriesByTeam, rankLabel, restLabel, spreadMoveLabel, statValue, totalMoveLabel } from './nflGameNotes'

const OPENED = '2026-09-18T17:42:18Z'
const LATEST = '2026-09-23T15:41:15Z'

function move(market: 'spread' | 'total', openLine: number, currentLine: number, change: number | null): NflLineMove {
  return { market, book: 'draftkings', openLine, openFetchedAt: OPENED, currentLine, currentFetchedAt: LATEST, move: change }
}

describe('spreadMoveLabel', () => {
  it('names the side the spread moved toward', () => {
    expect(spreadMoveLabel(move('spread', -6.5, -5.5, 1), 'GB', 'ATL')).toBe('GB -6.5 → GB -5.5 · 1.0 toward ATL')
    expect(spreadMoveLabel(move('spread', -3, -4.5, -1.5), 'GB', 'ATL')).toBe('GB -3.0 → GB -4.5 · 1.5 toward GB')
  })

  it('follows a flip of favorite through the book sign', () => {
    expect(spreadMoveLabel(move('spread', -1, 2, 3), 'CLE', 'PIT')).toBe('CLE -1.0 → PIT -2.0 · 3.0 toward PIT')
  })

  it('separates an unchanged line from a single stored line', () => {
    expect(spreadMoveLabel(move('spread', -7, -7, 0), 'BUF', 'LAC')).toBe('BUF -7.0 → BUF -7.0 · No change')
    expect(spreadMoveLabel(move('spread', 3, 3, null), 'CLE', 'PIT')).toBe('PIT -3.0 · One line stored, no movement yet')
  })
})

describe('totalMoveLabel', () => {
  it('says up or down with the size', () => {
    expect(totalMoveLabel(move('total', 46.5, 42.5, -4))).toBe('46.5 → 42.5 · down 4.0')
    expect(totalMoveLabel(move('total', 42.5, 44, 1.5))).toBe('42.5 → 44.0 · up 1.5')
  })

  it('does not call a single stored line unchanged', () => {
    expect(totalMoveLabel(move('total', 38.5, 38.5, null))).toBe('38.5 · One line stored, no movement yet')
    expect(totalMoveLabel(move('total', 50.5, 50.5, 0))).toBe('50.5 → 50.5 · No change')
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
