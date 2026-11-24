import { describe, expect, it } from 'vitest'
import type { PropLine } from '~/types/tennis'
import { playerPageOrigin } from '~/utils/tennisPlayerProps'
import { matchPropsPath, propMatchPath, readMatchView, updateMatchView } from '~/utils/tennisMatchView'

const players = { p1: { playerId: 44 }, p2: { playerId: 175 } }
const line: PropLine = {
  id: 321, matchId: 91823, playerId: 175, playerName: 'Kyrian Jacquet', source: 'prizepicks',
  statType: '1st Set Total Games', line: '9.5', oddsType: 'goblin', fetchedAt: '2026-10-22T17:00:00Z',
  startTime: null, pOver: null, pUnder: null, confidence: 'PASS',
}

describe('match view URL', () => {
  it('defaults ordinary match links to Analysis and public PrizePicks', () => {
    expect(readMatchView(new URLSearchParams(), players, false)).toEqual({
      tab: 'analysis', source: 'prizepicks', player: 'all', market: 'all',
    })
  })
  it('round trips a prop link with its source, player, market, and tab', () => {
    const path = propMatchPath(line)!
    expect(path.startsWith('/tennis/match/91823?')).toBe(true)
    expect(readMatchView(new URLSearchParams(path.split('?')[1]), players, false)).toEqual({
      tab: 'props', source: 'prizepicks', player: 175, market: '1st_set_total_games',
    })
  })
  it('ignores a retired prop selection in an old link', () => {
    expect(readMatchView(new URLSearchParams('tab=props&prop=321'), players, true)).not.toHaveProperty('prop')
  })
  it('rejects unknown players, tabs, and malformed market keys', () => {
    expect(readMatchView(new URLSearchParams('tab=other&player=999&market=<bad>'), players, true))
      .toMatchObject({ tab: 'analysis', player: 'all', market: 'all' })
  })
  it('keeps an owner source selection off the public view', () => {
    const query = new URLSearchParams('tab=props&source=dk')
    expect(readMatchView(query, players, false)).toMatchObject({ source: 'prizepicks' })
    expect(readMatchView(query, players, true)).toMatchObject({ source: 'dk' })
  })
  it('opens a retired Bet365 source link on PrizePicks', () => {
    expect(readMatchView(new URLSearchParams('tab=props&source=bet'), players, true)).toMatchObject({ source: 'prizepicks' })
  })
  it('updates only changed values and removes defaults without mutating history state', () => {
    const previous = new URLSearchParams('tab=props&player=175&market=aces&keep=yes')
    const next = updateMatchView(previous, { market: 'all' })
    expect(next.toString()).toBe('tab=props&player=175&keep=yes')
    expect(previous.get('market')).toBe('aces')
    expect(updateMatchView(next, { tab: 'analysis' }).has('tab')).toBe(false)
  })
})

describe('prop entry links', () => {
  it.each(['DraftKings', 'dk'])('preserves a supported source %s', source => {
    const query = new URLSearchParams(propMatchPath({ ...line, source })!.split('?')[1])
    expect(query.get('source')).toBe('dk')
    expect(query.has('prop')).toBe(false)
  })
  it.each(['Bet365', 'bet', 'fanduel'])('links a %s line to the props tab without a source', source => {
    expect(propMatchPath({ ...line, source })).toBe('/tennis/match/91823?tab=props')
  })
  it('keeps unlinked and invalid match IDs on their existing fallback', () => {
    expect(propMatchPath({ ...line, matchId: null })).toBeNull()
    expect(propMatchPath({ ...line, matchId: -1 })).toBeNull()
  })
  it('opens synthetic market/model rows on match picks', () => {
    expect(propMatchPath({ ...line, source: 'model', id: -321 })).toBe('/tennis/match/91823?tab=props')
  })
})

describe('matchPropsPath', () => {
  it('omits default filters', () => {
    expect(matchPropsPath(91823, { source: 'prizepicks', player: 'all', market: 'all' })).toBe('/tennis/match/91823?tab=props')
  })
  it('keeps the viewer filters, and the player page accepts the result as an origin', () => {
    const path = matchPropsPath(91823, { source: 'dk', player: 175, market: '1st_set_total_games' })
    expect(path).toBe('/tennis/match/91823?tab=props&source=dk&player=175&market=1st_set_total_games')
    expect(playerPageOrigin({ from: path })).toEqual({ path, label: 'Match props' })
  })
})
