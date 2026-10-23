import { describe, expect, it } from 'vitest'
import type { NbaLineMove, NbaPropLine, NbaSlateGame, NbaSlateGap } from '~/types/nba'
import { nbaGameGaps, nbaSlateCard, nbaSlateDigest, nbaSlateRow, nbaSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'

const NOW = new Date('2026-10-06T15:00:00Z')
const FETCHED = '2026-10-06T14:34:47Z'
const LATER = '2026-10-07T22:30:00Z'

function game(overrides: Partial<NbaSlateGame> = {}): NbaSlateGame {
  return {
    gameId: 21320, season: 2026, week: 1, gameType: 'REG', gameDate: '2026-10-20', startUtc: '2026-10-20T23:00:00Z',
    status: 'scheduled', awayTeam: 'BOS', homeTeam: 'DET', awayTeamName: 'Boston Celtics', homeTeamName: 'Detroit Pistons',
    awayScore: null, homeScore: null, awayRecord: { wins: 0, losses: 0 }, homeRecord: { wins: 0, losses: 0 }, propLineCount: 61,
    moneyline: { book: 'draftkings', homeOdds: -125, awayOdds: 105, homeWinProbability: 0.5325, fetchedAt: FETCHED },
    spread: { book: 'draftkings', homeLine: -2.5, homeOdds: -105, awayOdds: -115, fetchedAt: FETCHED },
    total: { book: 'draftkings', line: 221.5, overOdds: -110, underOdds: -110, fetchedAt: FETCHED },
    lineMovement: [],
    ...overrides,
  }
}

function moved(market: NbaLineMove['market'], openLine: number, currentLine: number, currentFetchedAt = LATER): NbaLineMove {
  return { market, book: 'draftkings', openLine, currentLine, openFetchedAt: FETCHED, currentFetchedAt }
}

describe('nbaSlateCard', () => {
  it('shows an upcoming game with the market, win bar and Central tip time', () => {
    const card = nbaSlateCard(game(), NOW)
    expect(card.state).toBe('upcoming')
    expect(card.stateLabel).toBeNull()
    expect(card.tip).toBe('Tue 6:00 PM CT')
    expect(card.away).toEqual({ code: 'BOS', name: 'Boston Celtics', record: 'No games yet', score: null, lost: false })
    expect(card.winBar).toEqual({ away: 47, home: 53 })
    expect(card.market).toEqual([
      { label: 'Spread', value: 'DET -2.5', detail: null },
      { label: 'Total', value: '221.5', detail: null },
      { label: 'Moneyline', value: 'DET -125', detail: 'BOS +105' },
    ])
    expect(card.final).toBeNull()
    expect(card.props).toBe('61 prop lines')
  })

  it('names the opening line once it moved, and says no move when it did not', () => {
    const card = nbaSlateCard(game({ lineMovement: [moved('spread', -1.5, -2.5), moved('total', 221.5, 221.5)] }), NOW)
    expect(card.market?.[0].detail).toBe('opened DET -1.5')
    expect(card.market?.[1].detail).toBe('no move')
  })

  it('gives no detail while only one row is stored', () => {
    const card = nbaSlateCard(game({ lineMovement: [moved('spread', -2.5, -2.5, FETCHED)] }), NOW)
    expect(card.market?.[0].detail).toBeNull()
  })

  it('puts an away favorite first and keeps a missing market as dashes', () => {
    const card = nbaSlateCard(game({
      moneyline: { book: 'fanduel', homeOdds: 140, awayOdds: -165, homeWinProbability: 0.4, fetchedAt: FETCHED }, spread: null,
    }), NOW)
    expect(card.market?.[0]).toEqual({ label: 'Spread', value: '--', detail: null })
    expect(card.market?.[2]).toEqual({ label: 'Moneyline', value: 'BOS -165', detail: 'DET +140' })
    expect(card.winBar).toEqual({ away: 60, home: 40 })
  })

  it('has no market or win bar when nothing is stored', () => {
    const card = nbaSlateCard(game({ moneyline: null, spread: null, total: null, propLineCount: 0 }), NOW)
    expect(card.market).toBeNull()
    expect(card.winBar).toBeNull()
    expect(card.props).toBe('No prop lines stored yet')
  })

  it('reads a game past tip-off that is not completed as started, not live', () => {
    const card = nbaSlateCard(game(), new Date('2026-10-21T02:00:00Z'))
    expect(card.state).toBe('started')
    expect(card.stateLabel).toBe('Tipped off')
    expect(card.market).not.toBeNull()
    expect(card.home.score).toBeNull()
  })

  it('grades a final against the closing lines', () => {
    const card = nbaSlateCard(game({
      status: 'completed', awayScore: 108, homeScore: 113, lineMovement: [moved('spread', -2.5, -3.5), moved('total', 221.5, 222.5)],
    }), NOW)
    expect(card.state).toBe('final')
    expect(card.away).toMatchObject({ score: 108, lost: true })
    expect(card.home).toMatchObject({ score: 113, lost: false })
    expect(card.final).toEqual([
      { label: 'Close spread', value: 'DET -3.5', detail: 'DET covered' },
      { label: 'Close total', value: '222.5', detail: 'under by 1.5' },
      { label: 'Props', value: '61', detail: 'lines' },
    ])
  })

  it('grades the other way, and a push', () => {
    const away = nbaSlateCard(game({ status: 'completed', awayScore: 110, homeScore: 109, lineMovement: [moved('total', 210.5, 210.5)] }), NOW)
    expect(away.final?.[0]).toEqual({ label: 'Close total', value: '210.5', detail: 'over by 8.5' })
    const push = nbaSlateCard(game({ status: 'completed', awayScore: 100, homeScore: 103, lineMovement: [moved('spread', -3, -3)] }), NOW)
    expect(push.final?.[0].detail).toBe('push')
    const cover = nbaSlateCard(game({ status: 'completed', awayScore: 100, homeScore: 101, lineMovement: [moved('spread', -2.5, -2.5)] }), NOW)
    expect(cover.final?.[0].detail).toBe('BOS covered')
  })

  it('has no graded lines for a final without closing lines', () => {
    const card = nbaSlateCard(game({ status: 'completed', awayScore: 108, homeScore: 113, moneyline: null, spread: null, total: null }), NOW)
    expect(card.final).toBeNull()
    expect(card.home.score).toBe(113)
  })

  it('shows a postponed game with no market', () => {
    const card = nbaSlateCard(game({ status: 'postponed' }), NOW)
    expect(card).toMatchObject({ state: 'off', stateLabel: 'Postponed', market: null, winBar: null, final: null })
    expect(nbaSlateCard(game({ status: 'canceled' }), NOW).stateLabel).toBe('Canceled')
  })

  it('shows a record once a team has played', () => {
    expect(nbaSlateCard(game({ homeRecord: { wins: 59, losses: 22 } }), NOW).home.record).toBe('59-22')
  })
})

describe('nbaSlateSummary', () => {
  it('counts games, prop lines and finals, and finds the latest odds fetch', () => {
    const games = [
      game(),
      game({ gameId: 2, propLineCount: 65, total: { book: 'draftkings', line: 230.5, overOdds: -105, underOdds: -115, fetchedAt: LATER } }),
      game({ gameId: 3, status: 'completed', propLineCount: 0, moneyline: null, spread: null, total: null }),
    ]
    expect(nbaSlateSummary(games)).toEqual({ games: 3, propLines: 126, finals: 1, oddsUpdated: 'Wed 5:30 PM CT' })
  })

  it('has no odds time without a market', () => {
    expect(nbaSlateSummary([]).oddsUpdated).toBeNull()
  })
})

describe('parseSlateDate', () => {
  it('keeps a real date and drops anything else', () => {
    expect(parseSlateDate('2026-10-20')).toBe('2026-10-20')
    expect(parseSlateDate('2026-02-30')).toBeNull()
    expect(parseSlateDate('garbage')).toBeNull()
    expect(parseSlateDate('2026-10-20T00:00')).toBeNull()
    expect(parseSlateDate(null)).toBeNull()
  })

  it('labels a slate date without shifting the day', () => {
    expect(slateDateLabel('2026-10-20')).toBe('Tue, Oct 20, 2026')
  })
})

describe('nbaSlateDigest', () => {
  const gap = (overrides: Partial<NbaSlateGap> = {}): NbaSlateGap => ({
    gameId: 21319, awayTeam: 'PHI', homeTeam: 'NY', playerId: 7, playerName: 'Jaylen Brown', market: 'points',
    line: 20.5, projection: 28.75, gap: 8.25, gapShare: 8.25 / 20.5, ...overrides,
  })

  it('formats line and model to one decimal with a signed gap and share', () => {
    expect(nbaSlateDigest([gap()])).toEqual([{
      key: '21319-7-points', gameId: 21319, playerId: 7, playerName: 'Jaylen Brown', marketKey: 'points', market: 'Points', matchup: 'PHI @ NY',
      line: '20.5', model: '28.8', gap: '+8.3 · +40%',
    }])
  })

  it('signs an under gap negative and labels combo markets', () => {
    const [item] = nbaSlateDigest([gap({ market: 'points_rebounds_assists', line: 27.5, projection: 23.55, gap: -3.95, gapShare: 3.95 / 27.5 })])
    expect(item.market).toBe('Pts + reb + ast')
    expect(item.gap).toBe('-4.0 · -14%')
  })

  it('keeps the API order and gives an empty strip for no items', () => {
    const items = nbaSlateDigest([gap({ playerId: 1 }), gap({ playerId: 2, market: 'blocks' })])
    expect(items.map(item => item.key)).toEqual(['21319-1-points', '21319-2-blocks'])
    expect(nbaSlateDigest([])).toEqual([])
  })
})

describe('nbaSlateRow', () => {
  it('reads an upcoming game from the card market', () => {
    const row = nbaSlateRow(game({ lineMovement: [moved('spread', -1.5, -2.5)] }), NOW)
    expect(row).toMatchObject({
      gameId: 21320, state: 'upcoming', tip: nbaSlateCard(game(), NOW).tip,
      spread: { value: 'DET -2.5', detail: 'opened DET -1.5' }, total: { value: '221.5', detail: null },
      moneyline: { value: 'DET -125', detail: 'BOS +105' }, win: 'DET 53%', props: 61, tags: [], note: null,
    })
    expect(row.away).toMatchObject({ code: 'BOS', record: 'No games yet', score: null })
  })

  it('tags a tipped-off game and keeps its latest market', () => {
    const row = nbaSlateRow(game(), new Date('2026-10-20T23:30:00Z'))
    expect(row.state).toBe('started')
    expect(row.tags).toEqual(['Tipped off'])
    expect(row.note).toBe('Scores load the morning after')
    expect(row.spread.value).toBe('DET -2.5')
  })

  it('grades a final against the close and drops the moneyline and win', () => {
    const row = nbaSlateRow(game({
      status: 'completed', awayScore: 110, homeScore: 104,
      lineMovement: [moved('spread', -1.5, -2.5), moved('total', 220.5, 221.5)],
    }), NOW)
    expect(row).toMatchObject({
      state: 'final', tip: 'Final',
      spread: { value: 'DET -2.5', detail: 'BOS covered' }, total: { value: '221.5', detail: 'under by 7.5' },
      moneyline: { value: '--', detail: null }, win: null, tags: [],
    })
    expect(row.away).toMatchObject({ score: 110, lost: false })
    expect(row.home).toMatchObject({ score: 104, lost: true })
  })

  it('shows a final without stored lines as dashes', () => {
    const row = nbaSlateRow(game({ status: 'completed', awayScore: 110, homeScore: 104 }), NOW)
    expect([row.spread.value, row.total.value]).toEqual(['--', '--'])
  })

  it('names a postponed game in the tip column with no market', () => {
    const row = nbaSlateRow(game({ status: 'postponed' }), NOW)
    expect(row).toMatchObject({ state: 'off', tip: 'Postponed', spread: { value: '--' }, moneyline: { value: '--' }, win: null })
    expect(nbaSlateRow(game({ status: 'canceled' }), NOW).tip).toBe('Canceled')
  })

  it('shows dashes and no win without a market', () => {
    const row = nbaSlateRow(game({ moneyline: null, spread: null, total: null }), NOW)
    expect([row.spread.value, row.total.value, row.moneyline.value, row.win]).toEqual(['--', '--', '--', null])
  })
})

describe('nbaGameGaps', () => {
  function line(overrides: Partial<NbaPropLine> = {}): NbaPropLine {
    return {
      playerId: 1, playerName: 'A Player', position: 'G', team: 'BOS', market: 'points', oddsType: 'standard', line: 20.5,
      fetchedAt: FETCHED, recent: [], injury: null, projection: 22.5, gamesInSample: 20, priorMinutes: 30, gap: 2,
      pOver: null, pUnder: null, overProbabilityVersion: null, flags: [], ...overrides,
    }
  }

  it('ranks standard projected lines by gap share, one per player, up to the limit', () => {
    const lines = [
      line({ playerId: 1, playerName: 'Big Gap', market: 'assists', line: 4.5, projection: 6.5, gap: 2 }),
      line({ playerId: 1, playerName: 'Big Gap', market: 'points', line: 10.5, projection: 14.5, gap: 4 }),
      line({ playerId: 2, playerName: 'Small Gap', line: 20.5, projection: 21.5, gap: 1 }),
      line({ playerId: 3, playerName: 'Goblin', oddsType: 'goblin', line: 2.5, projection: 6, gap: 3.5 }),
      line({ playerId: 4, playerName: 'No Projection', projection: null, gap: null }),
    ]
    const items = nbaGameGaps(game(), lines, NOW, 2)
    expect(items.map(item => [item.playerName, item.market])).toEqual([['Big Gap', 'assists'], ['Small Gap', 'points']])
    expect(items[0]).toMatchObject({ gameId: 21320, awayTeam: 'BOS', homeTeam: 'DET', gapShare: 2 / 4.5 })
  })

  it('is empty once the game has tipped or is not scheduled', () => {
    expect(nbaGameGaps(game({ startUtc: '2026-10-06T14:00:00Z' }), [line()], NOW)).toEqual([])
    expect(nbaGameGaps(game({ status: 'completed' }), [line()], NOW)).toEqual([])
    expect(nbaGameGaps(game({ startUtc: null }), [line()], NOW)).toEqual([])
  })
})
