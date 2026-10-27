import { describe, expect, it } from 'vitest'
import type { PropLine } from '~/types/tennis'
import { propMatchPath, readMatchView, updateMatchView } from '~/utils/tennisMatchView'

const players = { p1: { playerId: 44 }, p2: { playerId: 175 } }
const line: PropLine = {
  id: 321, matchId: 91823, playerId: 175, playerName: 'Kyrian Jacquet', source: 'prizepicks',
  statType: '1st Set Total Games', line: '9.5', oddsType: 'goblin', fetchedAt: '2026-10-22T17:00:00Z',
  startTime: null, pOver: null, pUnder: null, confidence: 'PASS',
}

describe('match view URL', () => {
  it('defaults ordinary match links to Analysis and public PrizePicks', () => {
    expect(readMatchView(new URLSearchParams(), players, false)).toEqual({
      tab: 'analysis', source: 'prizepicks', player: 'all', market: 'all', prop: null,
    })
  })
  it('round trips a selected prop with its source, player, market, and tab', () => {
    const path = propMatchPath(line)!
    expect(path.startsWith('/tennis/match/91823?')).toBe(true)
    expect(readMatchView(new URLSearchParams(path.split('?')[1]), players, false)).toEqual({
      tab: 'props', source: 'prizepicks', player: 175, market: '1st_set_total_games', prop: 321,
    })
  })
  it.each(['0', '-5', '1.5', '12abc', '9007199254740992'])('rejects invalid prop IDs %s', prop => {
    expect(readMatchView(new URLSearchParams({ prop }), players, true).prop).toBeNull()
  })
  it('rejects unknown players, tabs, and malformed market keys', () => {
    expect(readMatchView(new URLSearchParams('tab=other&player=999&market=<bad>'), players, true))
      .toMatchObject({ tab: 'analysis', player: 'all', market: 'all' })
  })
  it('cannot retarget an owner source selection to a public source line with the same ID', () => {
    const query = new URLSearchParams('tab=props&source=dk&prop=321')
    expect(readMatchView(query, players, false)).toMatchObject({ source: 'prizepicks', prop: null })
    expect(readMatchView(query, players, true)).toMatchObject({ source: 'dk', prop: 321 })
  })
  it('opens a retired Bet365 source link on PrizePicks', () => {
    expect(readMatchView(new URLSearchParams('tab=props&source=bet&prop=321'), players, true))
      .toMatchObject({ source: 'prizepicks', prop: null })
  })
  it('drops the selected ID if its source is invalid', () => {
    expect(readMatchView(new URLSearchParams('source=unknown&prop=321'), players, true).prop).toBeNull()
  })
  it('updates only changed values and removes defaults without mutating history state', () => {
    const previous = new URLSearchParams('tab=props&player=175&market=aces&prop=321&keep=yes')
    const next = updateMatchView(previous, { market: 'all', prop: null })
    expect(next.toString()).toBe('tab=props&player=175&keep=yes')
    expect(previous.get('prop')).toBe('321')
    expect(updateMatchView(next, { tab: 'analysis' }).has('tab')).toBe(false)
  })
})

describe('prop entry links', () => {
  it.each(['DraftKings', 'dk'])('preserves a supported source %s', source => {
    const query = new URLSearchParams(propMatchPath({ ...line, source })!.split('?')[1])
    expect(query.get('source')).toBe('dk')
    expect(query.get('prop')).toBe('321')
  })
  it.each(['Bet365', 'bet', 'fanduel'])('links a %s line to the props tab without a source', source => {
    expect(propMatchPath({ ...line, source })).toBe('/tennis/match/91823?tab=props')
  })
  it('keeps unlinked and invalid match IDs on their existing fallback', () => {
    expect(propMatchPath({ ...line, matchId: null })).toBeNull()
    expect(propMatchPath({ ...line, matchId: -1 })).toBeNull()
  })
  it('opens synthetic market/model rows on match picks without claiming a stored prop selection', () => {
    expect(propMatchPath({ ...line, source: 'model', id: -321 })).toBe('/tennis/match/91823?tab=props')
  })
})
