import { describe, expect, it } from 'vitest'
import type { NhlSlateGame } from '~/types/nhl'
import type { NhlGameContext, NhlGoalieSide, NhlInjury } from '~/types/nhlContext'
import { nhlSlateContext, unavailableNhlContext } from '~/utils/nhlContext'
import type { NhlGameState } from '~/utils/nhlGame'
import { nhlNoteTags, nhlSlateRow, nhlWinLabel } from '~/utils/nhlSlate'

const NOW = new Date('2026-10-23T18:00:00Z')
const START = '2026-10-24T00:00:00Z'
const FRESH = '2026-10-23T15:00:00Z'
const STALE = '2026-10-23T10:00:00Z'
// The slate's newest fetch, from a later run than a game fetched at FRESH.
const LATER_RUN = Date.parse('2026-10-23T17:30:00Z')

function goalie(team: string, overrides: Partial<NhlGoalieSide> = {}): NhlGoalieSide {
  return {
    team, espnAthleteId: '1', playerId: 8474593, playerName: 'Jacob Markstrom', status: 'expected',
    rawStatus: 'Expected', linkReason: 'matched', ...overrides,
  }
}

function injury(team: string): NhlInjury {
  return {
    espnAthleteId: '2', playerId: 1, playerName: 'Some Skater', team, status: 'Out', detail: null,
    sourceUpdatedAt: null, returnDate: null, linkReason: 'matched', teamMismatch: false,
  }
}

interface ContextOptions {
  away?: Partial<NhlGoalieSide>
  home?: Partial<NhlGoalieSide>
  awayInjuries?: number
  homeInjuries?: number
  goaliesFetched?: string | null
  injuriesFetched?: string | null
}

function context(options: ContextOptions = {}): NhlGameContext {
  const source = (fetchedAt: string | null) => ({
    source: 'ESPN' as const, fetchedAt, sourceTimestamp: null, freshness: fetchedAt === null ? 'unavailable' as const : 'fresh' as const,
  })
  const injuries = (team: string, count = 0) => Array.from({ length: count }, () => injury(team))
  return {
    injuries: {
      ...source(options.injuriesFetched === undefined ? FRESH : options.injuriesFetched),
      away: injuries('FLA', options.awayInjuries), home: injuries('BOS', options.homeInjuries),
    },
    goalies: {
      ...source(options.goaliesFetched === undefined ? FRESH : options.goaliesFetched),
      away: goalie('FLA', options.away), home: goalie('BOS', { playerName: 'Jeremy Swayman', ...options.home }),
    },
  }
}

function tags(report: NhlGameContext | undefined, state: NhlGameState = 'upcoming') {
  return nhlNoteTags(nhlSlateContext(report, 'FLA', 'BOS', START, NOW), state, 'FLA', 'BOS')
}

describe('nhlNoteTags', () => {
  it('tags expected and confirmed goalies by team and surname', () => {
    expect(tags(context({ home: { status: 'confirmed' } }))).toEqual(['FLA G Markstrom exp.', 'BOS G Swayman conf.'])
  })
  it('skips a team whose goalie is not reported', () => {
    const report = context({ away: { status: 'not_reported', playerName: null, playerId: null } })
    expect(tags(report)).toEqual(['BOS G Swayman exp.'])
  })
  it('marks a goalie name with no linked player', () => {
    expect(tags(context({ away: { playerId: null, linkReason: 'no_candidate' } }))[0]).toBe('FLA G Markstrom? exp.')
  })
  it('counts injuries per team with at least one', () => {
    expect(tags(context({ homeInjuries: 3 })).slice(2)).toEqual(['BOS 3 inj.'])
    expect(tags(context({ awayInjuries: 1, homeInjuries: 2 })).slice(2)).toEqual(['FLA 1 inj.', 'BOS 2 inj.'])
  })
  it('adds nothing for an empty injury report', () => {
    expect(tags(context())).toEqual(['FLA G Markstrom exp.', 'BOS G Swayman exp.'])
  })
  it('adds one stale tag when either report is stale', () => {
    expect(tags(context({ goaliesFetched: STALE })).at(-1)).toBe('reports stale')
    expect(tags(context({ goaliesFetched: STALE, injuriesFetched: STALE })).filter(tag => tag === 'reports stale')).toHaveLength(1)
  })
  it('names the one report that is unavailable', () => {
    expect(tags(context({ goaliesFetched: null, homeInjuries: 1 }))).toEqual(['BOS 1 inj.', 'no goalie report'])
    expect(tags(context({ injuriesFetched: null }))).toEqual(['FLA G Markstrom exp.', 'BOS G Swayman exp.', 'no injury report'])
  })
  it('shows one tag, not two, when both reports are unavailable', () => {
    expect(tags(context({ goaliesFetched: null, injuriesFetched: null }))).toEqual(['no ESPN report'])
    expect(tags(undefined)).toEqual(['no ESPN report'])
    expect(tags(unavailableNhlContext('FLA', 'BOS'))).toEqual(['no ESPN report'])
  })
  it.each(['final', 'off'] as const)('shows no tags on a %s game', state => {
    expect(tags(context({ homeInjuries: 2 }), state)).toEqual([])
  })
  it('keeps tags once the puck has dropped', () => {
    expect(tags(context(), 'started')).toHaveLength(2)
  })
})

function game(homeWinProbability: number | null): NhlSlateGame {
  return {
    gameId: 1, season: 2026, week: 2, gameType: 'REG', gameDate: '2026-10-23', startUtc: START,
    status: 'scheduled', awayTeam: 'FLA', homeTeam: 'BOS', awayTeamName: 'Florida Panthers', homeTeamName: 'Boston Bruins',
    awayScore: null, homeScore: null, endPeriod: null, awayRecord: { wins: 0, losses: 0, otLosses: 0 }, homeRecord: { wins: 0, losses: 0, otLosses: 0 }, propLineCount: 0,
    moneyline: homeWinProbability === null ? null
      : { book: 'draftkings', homeOdds: -130, awayOdds: 110, homeWinProbability, fetchedAt: FRESH },
    spread: null, total: null, lineMovement: [], context: unavailableNhlContext('FLA', 'BOS'),
  }
}

describe('nhlWinLabel', () => {
  it('shows the home favorite with one decimal', () => {
    expect(nhlWinLabel(game(0.564), 'upcoming')).toBe('BOS 56.4%')
  })
  it('shows the away favorite as the complement', () => {
    expect(nhlWinLabel(game(0.436), 'started')).toBe('FLA 56.4%')
  })
  it('gives a 50/50 game to the home side', () => {
    expect(nhlWinLabel(game(0.5), 'upcoming')).toBe('BOS 50.0%')
  })
  it('is empty with no moneyline', () => {
    expect(nhlWinLabel(game(null), 'upcoming')).toBeNull()
  })
  it.each(['final', 'off'] as const)('is empty on a %s game', state => {
    expect(nhlWinLabel(game(0.564), state)).toBeNull()
  })
})

describe('nhlSlateRow', () => {
  it('keeps each market to its value and detail, with no book or fetch time', () => {
    const row = nhlSlateRow({
      ...game(0.564), context: context({ homeInjuries: 3 }),
      spread: { book: 'bet365', homeLine: -1.5, homeOdds: 180, awayOdds: -222, fetchedAt: FRESH },
    }, NOW)
    expect(row.puckLine).toEqual({ value: 'BOS -1.5 (+180)', detail: 'FLA +1.5 (-222)' })
    expect(row.total).toEqual({ value: '--', detail: 'Not stored' })
    expect(row.moneyline).toEqual({ value: 'BOS -130', detail: 'FLA +110' })
    expect(row.win).toBe('BOS 56.4%')
    expect(row.tags).toEqual(['FLA G Markstrom exp.', 'BOS G Swayman exp.', 'BOS 3 inj.'])
  })
  it('gives a row its odds age only while the slate odds are stale and the game is not settled', () => {
    // NOW is Fri Oct 23, 1:00 PM CT; the moneyline was fetched at 10:00 AM.
    expect(nhlSlateRow(game(0.564), NOW, LATER_RUN).oddsAge).toBe('as of 10:00 AM')
    expect(nhlSlateRow(game(0.564), NOW).oddsAge).toBeNull()
    expect(nhlSlateRow(game(0.564), NOW, Date.parse('2026-10-23T15:30:00Z')).oddsAge).toBeNull()
    expect(nhlSlateRow(game(null), NOW, LATER_RUN).oddsAge).toBeNull()
    expect(nhlSlateRow({ ...game(0.564), status: 'completed', awayScore: 2, homeScore: 3 }, NOW, LATER_RUN).oddsAge).toBeNull()
  })
  it('drops the win label and tags once final, keeping the score', () => {
    const row = nhlSlateRow({ ...game(0.564), context: context(), status: 'completed', awayScore: 2, homeScore: 3 }, NOW)
    expect(row).toMatchObject({ state: 'final', win: null, tags: [], away: { score: 2 }, home: { score: 3 } })
  })
})
