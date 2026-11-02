import { describe, expect, it } from 'vitest'
import type { MatchPrediction, PlayerMatchLogRow } from '~/types/tennis'
import type { TennisBoardCategory, TennisBoardLine } from '~/utils/tennisPropBoard'
import { recentStatBars } from '~/utils/tennisPropCards'
import { formShortNote, formWindowOptions, formWindowSample, isPlayerLine, logRowToRecent, matchOptions, parseTennisFormWindow, playerMarketTabs, resolveFormWindow } from '~/utils/tennisPlayerProps'

function line(id: number, overrides: Partial<TennisBoardLine> = {}): TennisBoardLine {
  return { id, playerId: 7, playerName: 'Coco Gauff', matchId: 10, statType: 'aces', matchup: 'Coco Gauff vs Iga Swiatek', startTime: '2026-09-21T16:00:00Z', ...overrides } as TennisBoardLine
}

function category(market: string, rateable: TennisBoardLine[], other: TennisBoardLine[] = []): TennisBoardCategory {
  return { market, label: market, rateable, other }
}

function logRow(day: number, overrides: Partial<PlayerMatchLogRow> = {}): PlayerMatchLogRow {
  return {
    matchId: day, matchDate: `2026-08-${String(day).padStart(2, '0')}`, tournament: null, round: null, surface: null, bestOf: 3,
    opponentId: 100 + day, opponentName: `Opp ${day}`, opponentRank: null, result: 'W', score: '6-4 6-4',
    aces: day, doubleFaults: 1, bpSaved: null, bpFaced: null, bpWon: 2, bpCreated: 5, ...overrides,
  }
}

const twelve = Array.from({ length: 12 }, (_, index) => logRow(index + 1))

describe('isPlayerLine', () => {
  it('matches by id when the line has one, ignoring a same-name line for another id', () => {
    expect(isPlayerLine(line(1), 7, 'Coco Gauff')).toBe(true)
    expect(isPlayerLine(line(1, { playerId: 8 }), 7, 'Coco Gauff')).toBe(false)
  })

  it('falls back to the normalized name when the line has no id', () => {
    expect(isPlayerLine(line(1, { playerId: null, playerName: '  coco GAUFF ' }), 7, 'Coco Gauff')).toBe(true)
    expect(isPlayerLine(line(1, { playerId: null, playerName: null }), 7, 'Coco Gauff')).toBe(false)
  })
})

describe('playerMarketTabs', () => {
  it('keeps only this player\'s lines and drops markets without one', () => {
    const tabs = playerMarketTabs([
      category('aces', [line(1), line(2, { playerId: 8 })]),
      category('double_faults', [line(3, { playerId: 8 })]),
    ], 7, 'Coco Gauff')
    expect(tabs.map(tab => [tab.market, tab.rated.map(row => row.id)])).toEqual([['aces', [1]]])
  })

  it('still gives a tab for a market with only lines for review', () => {
    const [tab] = playerMarketTabs([category('winners', [], [line(4, { statType: 'winners' })])], 7, 'Coco Gauff')
    expect(tab.rated).toEqual([])
    expect(tab.review.map(row => row.id)).toEqual([4])
  })
})

describe('matchOptions', () => {
  const predictions = [
    { matchId: 10, startUtc: '2026-09-21T16:00:00Z', p1Id: 7, p2Id: 9, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' },
    { matchId: 11, startUtc: '2026-09-22T09:00:00Z', p1Id: 12, p2Id: 7, p1Name: 'Jessica Pegula', p2Name: 'Coco Gauff' },
  ] as MatchPrediction[]

  it('groups lines by match, earliest first, with the opponent from either side', () => {
    const options = matchOptions([line(1, { matchId: 11, startTime: null }), line(2), line(3)], predictions, 7, 'Coco Gauff')
    expect(options.map(option => [option.matchId, option.opponentId, option.opponentName])).toEqual([[10, 9, 'Iga Swiatek'], [11, 12, 'Jessica Pegula']])
  })

  it('has no opponent for a match missing from the predictions', () => {
    expect(matchOptions([line(1, { matchId: 99 })], predictions, 7, 'Coco Gauff')[0]).toMatchObject({ opponentId: null, opponentName: null })
  })

  it('uses the name when the prediction has no ids', () => {
    const [option] = matchOptions([line(1)], [{ ...predictions[0], p1Id: null, p2Id: null }], 7, 'Coco Gauff')
    expect(option).toMatchObject({ opponentId: null, opponentName: 'Iga Swiatek' })
  })
})

describe('form windows', () => {
  it('Last 5 is the newest five log rows whatever the log order', () => {
    const sample = formWindowSample([...twelve].reverse(), '5', null)
    expect(sample.map(match => match.matchDate)).toEqual(['2026-08-12', '2026-08-11', '2026-08-10', '2026-08-09', '2026-08-08'])
  })

  it('Last 10 caps at ten and reports a short sample', () => {
    expect(formWindowSample(twelve, '10', null)).toHaveLength(10)
    expect(formShortNote('10', formWindowSample(twelve.slice(0, 7), '10', null).length)).toBe('7 of 10 matches')
    expect(formShortNote('10', 10)).toBeNull()
    expect(formShortNote('5', 3)).toBeNull()
  })

  it('vs Opponent keeps only meetings with that opponent id', () => {
    const log = [logRow(1, { opponentId: 9 }), logRow(2), logRow(3, { opponentId: 9 })]
    expect(formWindowSample(log, 'opp', 9).map(match => match.matchDate)).toEqual(['2026-08-03', '2026-08-01'])
    expect(formWindowSample(log, 'opp', null)).toEqual([])
  })

  it('disables vs Opponent without an opponent id or any meeting, and falls back to Last 5', () => {
    const noId = formWindowOptions(twelve, null, null)
    expect(noId[2].disabledReason).toBe('No opponent for this match')
    const noMeeting = formWindowOptions(twelve, 999, 'Iga Swiatek')
    expect(noMeeting[2]).toMatchObject({ label: 'vs Iga Swiatek', disabledReason: 'No earlier matches against Iga Swiatek' })
    expect(resolveFormWindow(noMeeting, 'opp')).toBe('5')
    const met = formWindowOptions(twelve, 105, 'Opp 5')
    expect(met[2].disabledReason).toBeNull()
    expect(resolveFormWindow(met, 'opp')).toBe('opp')
    expect(resolveFormWindow(met, '10')).toBe('10')
  })

  it('reads the form from the URL, defaulting to Last 5', () => {
    expect(parseTennisFormWindow(new URLSearchParams('form=10'))).toBe('10')
    expect(parseTennisFormWindow(new URLSearchParams('form=opp'))).toBe('opp')
    expect(parseTennisFormWindow(new URLSearchParams('form=bogus'))).toBe('5')
    expect(parseTennisFormWindow(new URLSearchParams())).toBe('5')
  })
})

describe('logRowToRecent', () => {
  it('maps break points won to converted and created to chances', () => {
    expect(logRowToRecent(logRow(3))).toMatchObject({ breakPointsConverted: 2, breakChancesCreated: 5, aces: 3, doubleFaults: 1, result: 'W' })
  })

  it('feeds the bars: aces from the box score, no bars for a market the score cannot settle', () => {
    const recent = formWindowSample(twelve, '5', null)
    expect(recentStatBars(recent, 'aces', 9.5)?.map(bar => bar.value)).toEqual([8, 9, 10, 11, 12])
    expect(recentStatBars(recent, 'moneyline', 0)).toBeNull()
  })

  it('leaves a retirement out of a games market instead of drawing zero', () => {
    const recent = [logRowToRecent(logRow(1, { score: '6-3 2-0 RET' }))]
    expect(recentStatBars(recent, 'total_games', 20.5)?.[0].value).toBeNull()
  })
})
