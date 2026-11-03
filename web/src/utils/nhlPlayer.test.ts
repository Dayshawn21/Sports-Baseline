import { describe, expect, it } from 'vitest'
import type { NhlPlayerGame, NhlPlayerInjury, NhlPlayerLine, NhlPlayerMarket } from '~/types/nhl'
import { formDateText, formEmptyText, formHistoryDate, formOptions, formSample, formShortNote, type FormRow } from '~/utils/nflFormWindow'
import { nhlContextSource } from '~/utils/nhlContext'
import {
  NHL_HISTORY_FROM_YEAR, NHL_SEASON_START_MONTH, nhlChartLine, nhlFormRow, nhlFormSample, nhlNotLoadedCount,
  nhlPlayerInjuryReport, nhlPlayerPath, nhlPlayerStatus, nhlPlayerTabs, nhlSampleNote, nhlSelectedMarket,
} from '~/utils/nhlPlayer'

const game = (day: number, value: number | null, opponent: string | null = 'WSH'): NhlPlayerGame => ({ gameDate: `2026-10-${String(day).padStart(2, '0')}`, opponent, value })
const rung = (line: number, oddsType: NhlPlayerLine['oddsType']): NhlPlayerLine => ({ line, oddsType, fetchedAt: '2026-11-02T15:00:00Z' })

function market(overrides: Partial<NhlPlayerMarket> = {}): NhlPlayerMarket {
  return {
    market: 'shots_on_goal',
    lines: [rung(2.5, 'goblin'), rung(3.5, 'standard'), rung(4.5, 'demon')],
    recent: Array.from({ length: 10 }, (_, index) => game(30 - index, index === 1 ? null : index)),
    opponentGames: [game(3, 2), game(2, null)],
    ...overrides,
  }
}

describe('nhlPlayerPath', () => {
  it('leaves empty options off the URL', () => {
    expect(nhlPlayerPath(7)).toBe('/nhl/player/7')
    expect(nhlPlayerPath(7, { date: null, market: '' })).toBe('/nhl/player/7')
  })

  it('carries the date and market when given', () => {
    expect(nhlPlayerPath(7, { date: '2026-11-02' })).toBe('/nhl/player/7?date=2026-11-02')
    expect(nhlPlayerPath(7, { date: '2026-11-02', market: 'points' })).toBe('/nhl/player/7?date=2026-11-02&market=points')
  })
})

describe('nhlPlayerTabs and nhlSelectedMarket', () => {
  const tabs = nhlPlayerTabs([{ market: 'points' }, { market: 'assists' }, { market: 'points' }])

  it('keeps the API order and lists a market once', () => {
    expect(tabs).toEqual(['points', 'assists'])
  })

  it('selects the asked market, else the first, else none', () => {
    expect(nhlSelectedMarket(new URLSearchParams('market=assists'), tabs)).toBe('assists')
    expect(nhlSelectedMarket(new URLSearchParams('market=hits'), tabs)).toBe('points')
    expect(nhlSelectedMarket(new URLSearchParams(''), tabs)).toBe('points')
    expect(nhlSelectedMarket(new URLSearchParams('market=points'), [])).toBeNull()
  })
})

describe('nhlFormSample', () => {
  it('drops a game with no stored value and averages the rest to two places', () => {
    const sample = nhlFormSample([game(3, 1), game(2, null), game(1, 2)])
    expect(sample.values.map(item => item.value)).toEqual([1, 2])
    expect(sample.average).toBe(1.5)
  })

  it('keeps zero and negative values as real values', () => {
    const sample = nhlFormSample([game(3, 0), game(2, -2), game(1, 1)])
    expect(sample.values.map(item => item.value)).toEqual([0, -2, 1])
    expect(sample.average).toBe(-0.33)
  })

  it('has no average for an empty or all-unloaded sample', () => {
    expect(nhlFormSample([]).average).toBeNull()
    expect(nhlFormSample([game(1, null)])).toEqual({ average: null, values: [] })
  })
})

describe('nhlNotLoadedCount', () => {
  it('counts unloaded games inside the chosen window only', () => {
    const item = market()
    expect(nhlNotLoadedCount(item, '5')).toBe(1)
    expect(nhlNotLoadedCount(item, '10')).toBe(1)
    expect(nhlNotLoadedCount(item, 'opp')).toBe(1)
    expect(nhlNotLoadedCount(market({ recent: [game(9, 1), game(8, 1), game(7, 1), game(6, 1), game(5, 1), game(4, null)] }), '5')).toBe(0)
  })
})

describe('nhlChartLine', () => {
  it('prefers the standard rung over demon and goblin', () => {
    expect(nhlChartLine(market())).toBe(3.5)
  })

  it('is null with no standard rung, never a guess among alternates', () => {
    expect(nhlChartLine(market({ lines: [rung(2.5, 'goblin'), rung(4.5, 'demon')] }))).toBeNull()
  })
})

describe('nhlSampleNote', () => {
  it('says goalie samples are started games only', () => {
    expect(nhlSampleNote({ market: 'goalie_saves' })).toBe('Started games only')
    expect(nhlSampleNote({ market: 'goals_allowed' })).toBe('Started games only')
  })

  it('has no note for a skater market', () => {
    expect(nhlSampleNote({ market: 'shots_on_goal' })).toBeNull()
    expect(nhlSampleNote({ market: 'time_on_ice' })).toBeNull()
  })
})

describe('nhlPlayerStatus', () => {
  it('joins position, team, opponent and date', () => {
    expect(nhlPlayerStatus({ position: 'C', team: 'LAK', opponent: 'WSH', date: '2026-11-02' })).toBe('C · LAK · vs WSH · 2026-11-02')
  })

  it('leaves out what is missing', () => {
    expect(nhlPlayerStatus({ position: null, team: 'LAK', opponent: null, date: '2026-11-02' })).toBe('LAK · 2026-11-02')
  })
})

describe('nhlPlayerInjuryReport', () => {
  it('shapes the player block as the report the shared freshness helper reads', () => {
    const injury: NhlPlayerInjury = { fetchedAt: '2026-11-02T14:00:00Z', sourceTimestamp: '2026-11-02T13:00:00Z', freshness: 'fresh', entry: null }
    const report = nhlPlayerInjuryReport(injury)
    expect(report).toEqual({ source: 'ESPN', fetchedAt: '2026-11-02T14:00:00Z', sourceTimestamp: '2026-11-02T13:00:00Z', freshness: 'fresh' })
    const now = new Date('2026-11-02T15:00:00Z')
    expect(nhlContextSource(report, '2026-11-02T23:00:00Z', now).freshness).toBe('fresh')
  })

  it('reads as unavailable when the endpoint stored no report', () => {
    const none: NhlPlayerInjury = { fetchedAt: null, sourceTimestamp: null, freshness: 'unavailable', entry: null }
    expect(nhlContextSource(nhlPlayerInjuryReport(none), '2026-11-02T23:00:00Z', new Date('2026-11-02T15:00:00Z')).freshness).toBe('unavailable')
  })
})

describe('nhlFormRow with the shared form helpers', () => {
  const row: FormRow = nhlFormRow(market(), 'WSH')

  it('builds Last 5, Last 10 and the opponent window from the market', () => {
    expect(row.recentForm.values).toHaveLength(4)
    expect(row.recentFormLong?.values).toHaveLength(9)
    expect(row.opponentHistory?.values).toHaveLength(1)
    expect(formSample(row, 'opp').average).toBe(2)
  })

  it('names the short Last 10 and the empty opponent window with NHL years', () => {
    expect(formShortNote(row, '10')).toBe('9 of 10 games')
    const empty = nhlFormRow(market({ opponentGames: [] }), 'WSH')
    expect(formEmptyText(empty, 'opp', NHL_HISTORY_FROM_YEAR)).toBe('No earlier games against WSH since 2023.')
    expect(formOptions(nhlFormRow(market({ recent: [game(9, 1)] }), null)).find(option => option.window === 'opp')?.disabledReason).not.toBeNull()
  })

  it('dates games with the NHL season boundary, so a spring game this season shows no year in autumn', () => {
    const now = new Date('2026-11-02T12:00:00Z')
    expect(formDateText(formHistoryDate('2026-04-10', now, NHL_SEASON_START_MONTH))).toBe(`Apr 10 '26`)
    expect(formDateText(formHistoryDate('2026-10-20', now, NHL_SEASON_START_MONTH))).toBe('Oct 20')
  })
})
