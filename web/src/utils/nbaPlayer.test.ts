import { describe, expect, it } from 'vitest'
import type { NbaPlayerGame, NbaPlayerMarket, NbaPlayerRung } from '~/types/nba'
import { formEmptyText, formOptions, formSample, formShortNote } from '~/utils/nflFormWindow'
import { nbaChartLine, nbaFormRow, nbaFormSample, nbaNotLoadedCount, nbaPercentText, nbaPlayerPath, nbaPlayerStatus, nbaPlayerTabs, nbaRungNotes, NBA_HISTORY_FROM_YEAR, nbaSelectedMarket, nbaStandardLine } from '~/utils/nbaPlayer'

const game = (day: number, value: number | null, opponent: string | null = 'TOR'): NbaPlayerGame => ({ gameDate: `2026-10-${String(day).padStart(2, '0')}`, opponent, value })
const rung = (line: number, oddsType: string | null): NbaPlayerRung => ({ line, oddsType, fetchedAt: '2026-11-02T15:00:00Z', gap: null, pOver: null, pUnder: null, overProbabilityVersion: null, flags: [] })

function market(overrides: Partial<NbaPlayerMarket> = {}): NbaPlayerMarket {
  return {
    market: 'assists', kind: 'modelled', projection: 5, gamesInSample: 20, priorMinutes: 32,
    lines: [rung(3.5, 'goblin'), rung(4.5, 'standard'), rung(6.5, 'demon')],
    recent: Array.from({ length: 10 }, (_, index) => game(30 - index, index === 1 ? null : index)),
    opponentGames: [game(3, 2), game(2, null)],
    ...overrides,
  }
}

describe('nbaPlayerPath', () => {
  it('leaves empty options off the URL', () => {
    expect(nbaPlayerPath(7)).toBe('/nba/player/7')
    expect(nbaPlayerPath(7, { date: null, market: '' })).toBe('/nba/player/7')
  })

  it('carries the date and market when given', () => {
    expect(nbaPlayerPath(7, { date: '2026-11-02' })).toBe('/nba/player/7?date=2026-11-02')
    expect(nbaPlayerPath(7, { date: '2026-11-02', market: 'points' })).toBe('/nba/player/7?date=2026-11-02&market=points')
  })
})

describe('nbaPlayerTabs and nbaSelectedMarket', () => {
  const tabs = nbaPlayerTabs([{ market: 'points' }, { market: 'assists' }, { market: 'points' }])

  it('keeps the API order and lists a market once', () => {
    expect(tabs).toEqual(['points', 'assists'])
  })

  it('selects the asked market, else the first, else none', () => {
    expect(nbaSelectedMarket(new URLSearchParams('market=assists'), tabs)).toBe('assists')
    expect(nbaSelectedMarket(new URLSearchParams('market=steals'), tabs)).toBe('points')
    expect(nbaSelectedMarket(new URLSearchParams(), tabs)).toBe('points')
    expect(nbaSelectedMarket(new URLSearchParams('market=points'), [])).toBeNull()
  })
})

describe('nbaFormSample and nbaNotLoadedCount', () => {
  it('drops a game whose stat was not loaded instead of drawing a zero', () => {
    const sample = nbaFormSample([game(3, 2), game(2, null), game(1, 4)])
    expect(sample.values.map(item => item.value)).toEqual([2, 4])
    expect(sample.average).toBe(3)
    expect(sample.values[0]).toEqual({ value: 2, opponentTeam: 'TOR', gameDate: '2026-10-03' })
  })

  it('has no average for an empty sample and rounds to two places', () => {
    expect(nbaFormSample([]).average).toBeNull()
    expect(nbaFormSample([game(3, 1), game(2, 1), game(1, 2)]).average).toBe(1.33)
  })

  it('counts the unloaded games in the window asked for', () => {
    const data = market()
    expect(nbaNotLoadedCount(data, '5')).toBe(1)
    expect(nbaNotLoadedCount(data, '10')).toBe(1)
    expect(nbaNotLoadedCount(data, 'opp')).toBe(1)
    expect(nbaNotLoadedCount(market({ recent: [game(3, 1)] }), '10')).toBe(0)
  })
})

describe('nbaStandardLine', () => {
  it('picks the standard rung over demon and goblin', () => {
    expect(nbaStandardLine(market())).toBe(4.5)
  })

  it('has no line when there is no standard rung, never a guess', () => {
    expect(nbaStandardLine(market({ lines: [rung(3.5, 'goblin'), rung(6.5, 'demon')] }))).toBeNull()
    expect(nbaStandardLine(market({ lines: [rung(0.5, null)] }))).toBeNull()
  })
})

describe('nbaPlayerStatus', () => {
  it('names the opponent when there is one', () => {
    expect(nbaPlayerStatus({ position: 'G', team: 'LAC', opponent: 'TOR', date: '2026-11-02' })).toBe('G · LAC · vs TOR · 2026-11-02')
  })

  it('leaves out what is missing', () => {
    expect(nbaPlayerStatus({ position: null, team: 'LAC', opponent: null, date: '2026-11-02' })).toBe('LAC · 2026-11-02')
  })
})

describe('nbaPercentText', () => {
  it('rounds to a whole percent and shows a dash for no probability', () => {
    expect(nbaPercentText(0.5149)).toBe('51%')
    expect(nbaPercentText(0)).toBe('0%')
    expect(nbaPercentText(null)).toBe('--')
  })
})

describe('nbaRungNotes', () => {
  const flagged = (line: number, flags: NbaPlayerRung['flags']): NbaPlayerRung => ({ ...rung(line, 'standard'), flags })

  it('says a flag every rung shares once', () => {
    const notes = nbaRungNotes([flagged(4.5, ['low_minutes']), flagged(5.5, ['low_minutes'])])
    expect(notes.shared).toBe('No projection: under 20 minutes a game')
    expect(notes.perRung).toEqual([null, null])
  })

  it('keeps per-rung notes when the rungs differ', () => {
    const notes = nbaRungNotes([flagged(4.5, []), flagged(5, ['integer_line'])])
    expect(notes.shared).toBeNull()
    expect(notes.perRung).toEqual([null, 'Whole-number line: no P(over)'])
  })

  it('has no notes when no rung is flagged', () => {
    expect(nbaRungNotes([flagged(4.5, [])])).toEqual({ shared: null, perRung: [null] })
    expect(nbaRungNotes([])).toEqual({ shared: null, perRung: [] })
  })
})

describe('nbaFormRow', () => {
  const recent = (count: number) => Array.from({ length: count }, (_, index) => game(30 - index, index + 1))

  it('takes Last 5 from the first five games and Last 10 from all of them', () => {
    const row = nbaFormRow(market({ recent: recent(10) }), 'TOR')
    expect(row.recentForm.values.map(item => item.value)).toEqual([1, 2, 3, 4, 5])
    expect(row.recentFormLong?.values).toHaveLength(10)
    expect(row.opponentTeam).toBe('TOR')
  })

  it('drops a game whose stat was not loaded from every window', () => {
    const row = nbaFormRow(market({ recent: [game(9, null), game(8, 2)], opponentGames: [game(3, null), game(2, 4)] }), 'TOR')
    expect(row.recentForm.values.map(item => item.value)).toEqual([2])
    expect(row.opponentHistory.values.map(item => item.value)).toEqual([4])
  })

  it('shows at most the ten most recent games against the opponent', () => {
    const opponentGames = Array.from({ length: 20 }, (_, index) => game(30 - index, index))
    const row = nbaFormRow(market({ opponentGames }), 'TOR')
    expect(row.opponentHistory.values).toHaveLength(10)
    expect(row.opponentHistory.values[0].value).toBe(0)
  })

  it('has no opponent window label when there is no opponent', () => {
    const row = nbaFormRow(market(), null)
    expect(row.opponentTeam).toBeNull()
    expect(formOptions(row)[2].disabledReason).not.toBeNull()
  })

  it('feeds the shared helpers: a short Last 10 and the since-2023 empty text', () => {
    const row = nbaFormRow(market({ recent: recent(6), opponentGames: [] }), 'TOR')
    expect(formShortNote(row, '10')).toBe('6 of 10 games')
    expect(formSample(row, '10').values).toHaveLength(6)
    expect(formEmptyText(row, 'opp', NBA_HISTORY_FROM_YEAR)).toBe('No earlier games against TOR since 2023.')
  })
})

describe('nbaChartLine', () => {
  it('is the standard rung, and none for double-double or a market without one', () => {
    expect(nbaChartLine(market())).toBe(4.5)
    expect(nbaChartLine(market({ market: 'double_double', lines: [rung(0.5, 'standard')] }))).toBeNull()
    expect(nbaChartLine(market({ lines: [rung(3.5, 'goblin')] }))).toBeNull()
  })
})
