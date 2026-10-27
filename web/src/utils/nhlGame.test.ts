import { describe, expect, it } from 'vitest'
import type { NhlSlateGame } from '~/types/nhl'
import { unavailableNhlContext } from '~/utils/nhlContext'
import {
  nhlBookLabel, nhlGameState, nhlMarketCells, nhlMarketProbability, nhlPuckDropLabel,
  nhlTimeLabel, parseNhlGameId, signedNhlLine, validNhlGameId,
} from '~/utils/nhlGame'
import { nhlSlateRow, nhlSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nhlSlate'

const FETCHED = '2026-10-23T12:00:00Z'
const NOW = new Date('2026-10-23T18:00:00Z')

function game(overrides: Partial<NhlSlateGame> = {}): NhlSlateGame {
  return {
    gameId: 57029, season: 2026, week: 2, gameType: 'REG', gameDate: '2026-10-23', startUtc: '2026-10-24T00:00:00Z',
    status: 'scheduled', awayTeam: 'MTL', homeTeam: 'CHI', awayTeamName: 'Montreal Canadiens', homeTeamName: 'Chicago Blackhawks',
    awayScore: null, homeScore: null, endPeriod: null, propLineCount: 3,
    moneyline: { book: 'draftkings', homeOdds: -120, awayOdds: 110, homeWinProbability: 0.53, fetchedAt: FETCHED },
    spread: { book: 'bet365', homeLine: -1.5, homeOdds: 150, awayOdds: -180, fetchedAt: FETCHED },
    total: { book: 'draftkings', line: 6.5, overOdds: -110, underOdds: -115, fetchedAt: FETCHED },
    lineMovement: [], context: unavailableNhlContext('MTL', 'CHI'), ...overrides,
  }
}

describe('NHL link inputs', () => {
  it.each([undefined, '', '-1', '0', '1.5', '1e2', '+12', ' 12', '12x', '9007199254740992'])('rejects invalid id %s', value => {
    expect(parseNhlGameId(value)).toBeNull()
  })
  it('accepts positive safe integers, including leading zero links', () => {
    expect(parseNhlGameId('057029')).toBe(57029)
    expect(parseNhlGameId(String(Number.MAX_SAFE_INTEGER))).toBe(Number.MAX_SAFE_INTEGER)
  })
  it.each([null, 0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1])('disables numeric id %s', value => {
    expect(validNhlGameId(value)).toBe(false)
  })
  it.each([null, '', '2026-02-29', '2026-04-31', '0000-01-01', '2026-13-01', '2026-1-02', '2026-10-23T00:00:00Z'])('rejects invalid date %s', value => {
    expect(parseSlateDate(value)).toBeNull()
  })
  it('preserves real leap days and the named Eastern slate day', () => {
    expect(parseSlateDate('2024-02-29')).toBe('2024-02-29')
    expect(slateDateLabel('2026-10-23')).toBe('Fri, Oct 23, 2026')
  })
})

describe('NHL CT labels and game state', () => {
  it('formats summer and winter clocks with CT and retains the actual local day', () => {
    expect(nhlPuckDropLabel('2026-10-24T00:00:00Z')).toBe('Fri 7:00 PM CT')
    expect(nhlPuckDropLabel('2026-12-24T00:00:00Z')).toBe('Wed 6:00 PM CT')
    expect(nhlTimeLabel(FETCHED, true)).toBe('Oct 23, 2026, 7:00 AM CT')
  })
  it.each([null, 'not-a-time'])('handles missing or malformed timestamp %s', value => {
    expect(nhlPuckDropLabel(value)).toBe('Time TBD')
    expect(nhlTimeLabel(value)).toBe('--')
  })
  it('distinguishes scheduled from started at the exact start without claiming live data', () => {
    expect(nhlGameState(game(), NOW)).toEqual({ state: 'upcoming', label: 'Scheduled' })
    expect(nhlGameState(game({ startUtc: NOW.toISOString() }), NOW)).toEqual({ state: 'started', label: 'Puck dropped' })
    expect(nhlGameState(game({ startUtc: null }), NOW).state).toBe('upcoming')
  })
  it.each(['OT', 'SO'] as const)('preserves final %s context before clock state', endPeriod => {
    expect(nhlGameState(game({ status: 'completed', endPeriod }), NOW)).toEqual({ state: 'final', label: `Final / ${endPeriod}` })
  })
  it('handles REG finals, cancellations and postponements', () => {
    expect(nhlGameState(game({ status: 'completed', endPeriod: 'REG' }), NOW).label).toBe('Final')
    expect(nhlGameState(game({ status: 'canceled' }), NOW)).toEqual({ state: 'off', label: 'Canceled' })
    expect(nhlGameState(game({ status: 'postponed' }), NOW)).toEqual({ state: 'off', label: 'Postponed' })
  })
})

describe('NHL market display', () => {
  it('keeps both signed puck lines and each side price, book and timestamp', () => {
    const [puck, total, moneyline] = nhlMarketCells(game())
    expect(puck).toEqual({ label: 'Puck line', value: 'CHI -1.5 (+150)', detail: 'MTL +1.5 (-180)', book: 'bet365', fetchedAt: FETCHED })
    expect(total.value).toBe('6.5')
    expect(total.detail).toBe('Over -110 / Under -115')
    expect(moneyline.value).toBe('CHI -120')
    expect(moneyline.detail).toBe('MTL +110')
    expect(nhlBookLabel('draftkings')).toBe('DraftKings')
    expect(nhlBookLabel('fanduel')).toBe('FanDuel')
    expect(nhlBookLabel('bet365')).toBe('Bet365')
  })
  it('keeps a positive home puck line positive instead of relabeling it as a home favorite', () => {
    const original = game()
    const cells = nhlMarketCells(game({ spread: { ...original.spread!, homeLine: 1.5 } }))
    expect(cells[0].value).toBe('CHI +1.5 (+150)')
    expect(cells[0].detail).toBe('MTL -1.5 (-180)')
    expect(signedNhlLine(-0)).toBe('0.0')
  })
  it('attributes probability to the stored book and includes OT/SO', () => {
    expect(nhlMarketProbability(game())).toEqual({
      label: 'Market win probability', value: 'CHI 53.0% / MTL 47.0%',
      detail: 'De-vigged book probability, includes OT/SO', book: 'draftkings', fetchedAt: FETCHED,
    })
  })
  it('renders missing markets independently, without prices, probabilities or provenance', () => {
    const missing = game({ moneyline: null, spread: null })
    expect(nhlMarketCells(missing).map(cell => cell.value)).toEqual(['--', '6.5', '--'])
    expect(nhlMarketProbability(missing).book).toBeNull()
    expect(nhlMarketProbability(missing).value).toBe('--')
  })
})

describe('NHL slate derivations', () => {
  it('shows only completed scores, preserving zero and null values', () => {
    expect(nhlSlateRow(game({ awayScore: 0, homeScore: 2 }), NOW).away.score).toBeNull()
    const final = nhlSlateRow(game({ status: 'completed', endPeriod: 'SO', awayScore: 0, homeScore: 1 }), NOW)
    expect(final.away.score).toBe(0)
    expect(final.home.score).toBe(1)
    expect(final.stateLabel).toBe('Final / SO')
    expect(final.props).toBe(3)
    expect(nhlSlateRow(game({ status: 'completed' }), NOW).away.score).toBeNull()
  })
  it('reports empty days and the latest stored fetch, without altering input order', () => {
    expect(nhlSlateSummary([])).toEqual({ games: 0, propLines: 0, finals: 0, oddsUpdated: null })
    const first = game({ gameId: 2 })
    const second = game({ status: 'completed', propLineCount: 4, moneyline: { ...first.moneyline!, fetchedAt: '2026-10-23T14:00:00Z' } })
    const games = Object.freeze([first, second])
    expect(nhlSlateSummary(games)).toEqual({ games: 2, propLines: 7, finals: 1, oddsUpdated: 'Oct 23, 2026, 9:00 AM CT' })
    expect(games.map(item => item.gameId)).toEqual([2, 57029])
    expect(nhlSlateSummary([game({ moneyline: null, spread: null, total: null })]).oddsUpdated).toBeNull()
  })
})
