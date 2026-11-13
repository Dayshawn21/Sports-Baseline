import { describe, expect, it } from 'vitest'
import type { NbaPlayerGame, NbaPlayerMarket, NbaPlayerRung } from '~/types/nba'
import { nbaInjuryTime } from '~/utils/nbaInjuries'
import { formEmptyText, formOptions, formSample, formShortNote } from '~/utils/nflFormWindow'
import { nbaChartLine, nbaFormRow, nbaFormSample, nbaNotLoadedCount, nbaPercentText, nbaPlayerFooter, nbaPlayerPath, nbaPlayerStatus, nbaPlayerTabs, nbaProjectionHero, nbaRungNotes, NBA_HISTORY_FROM_YEAR, nbaSelectedMarket, nbaStandardLine } from '~/utils/nbaPlayer'

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
    expect(nbaPlayerStatus({ position: 'G', team: 'LAC', opponent: 'TOR', date: '2026-11-02', markets: [] })).toBe('G · LAC · vs TOR · 2026-11-02')
  })

  it('adds average minutes from the first market that carries them', () => {
    const markets = [market({ kind: 'line-only', gamesInSample: null, priorMinutes: null }), market({ priorMinutes: 25.06 })]
    expect(nbaPlayerStatus({ position: 'G', team: 'IND', opponent: 'NY', date: '2026-11-13', markets })).toBe('G · IND · vs NY · 2026-11-13 · 25.1 min')
  })

  it('leaves out what is missing', () => {
    const markets = [market({ kind: 'line-only', gamesInSample: null, priorMinutes: null })]
    expect(nbaPlayerStatus({ position: null, team: 'LAC', opponent: null, date: '2026-11-02', markets })).toBe('LAC · 2026-11-02')
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

describe('nbaProjectionHero', () => {
  it('shows the projection against the standard line with its sample', () => {
    const hero = nbaProjectionHero(market({ lines: [rung(3.5, 'goblin'), { ...rung(4.5, 'standard'), gap: 0.5 }] }))
    expect(hero).toEqual({
      label: 'Projected assists', value: '5.0', delta: '+0.5 vs 4.5 line', reason: null,
      sample: 'based on last 20 games', facts: [],
    })
  })

  it('says why a modelled market has no number', () => {
    const lowMinutes = market({ projection: null, priorMinutes: 16.4, gamesInSample: 28, lines: [{ ...rung(2.5, 'standard'), flags: ['low_minutes'] }] })
    expect(nbaProjectionHero(lowMinutes)?.reason).toBe('No projection: 16.4 minutes a game, under the 20-minute floor.')
    expect(nbaProjectionHero(lowMinutes)?.delta).toBeNull()
    const fewGames = market({ projection: null, gamesInSample: 6, lines: [{ ...rung(2.5, 'standard'), flags: ['few_prior_games'] }] })
    expect(nbaProjectionHero(fewGames)?.reason).toBe('No projection: 6 earlier games, under the 10-game minimum.')
  })

  it('draws nothing for a line-only market', () => {
    expect(nbaProjectionHero(market({ kind: 'line-only' }))).toBeNull()
  })
})


describe('nbaPlayerFooter', () => {
  const report = { source: 'ESPN' as const, fetchedAt: '2026-11-02T14:00:00Z', freshness: 'fresh' as const, injuries: [] }

  it('names the newest line, the injury report and the model', () => {
    const later = { ...rung(5.5, 'standard'), fetchedAt: '2026-11-02T16:30:00Z' }
    const text = nbaPlayerFooter({ markets: [market(), market({ lines: [later] })], injuryReport: report, modelVersion: 'nba-props-v2' })
    expect(text).toBe(`PrizePicks lines as of ${nbaInjuryTime('2026-11-02T16:30:00Z')}. ESPN injury report as of ${nbaInjuryTime('2026-11-02T14:00:00Z')}. Projections from nba-props-v2.`)
  })

  it('says what is missing', () => {
    const text = nbaPlayerFooter({ markets: [], injuryReport: { ...report, fetchedAt: null }, modelVersion: 'nba-props-v2' })
    expect(text).toBe('No PrizePicks lines stored. No ESPN injury report loaded. Projections from nba-props-v2.')
  })
})
