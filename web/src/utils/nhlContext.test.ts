import { describe, expect, it } from 'vitest'
import type { NhlContextSource, NhlGameContext, NhlInjury } from '~/types/nhlContext'
import { nhlContextFreshness, nhlContextSource, nhlContextTime, nhlGoalieLabel, nhlInjuryDetails, nhlSlateContext, unavailableNhlContext } from '~/utils/nhlContext'

const NOW = new Date('2026-10-24T19:00:00Z')
const START = '2026-10-25T00:00:00Z'
const source: NhlContextSource = { source: 'ESPN', fetchedAt: '2026-10-24T18:00:00Z', sourceTimestamp: null, freshness: 'fresh' }
function context(): NhlGameContext {
  const value = unavailableNhlContext('TBL', 'CHI')
  return { injuries: { ...value.injuries, ...source }, goalies: { ...value.goalies, ...source } }
}
const prepare = (value: NhlGameContext | undefined) => nhlSlateContext(value, 'TBL', 'CHI', START, NOW)

describe('NHL game source details', () => {
  const injury: NhlInjury = { espnAthleteId: '12', playerId: 4, playerName: 'Source Name', team: 'TBL', status: 'Questionable', detail: 'Source detail',
    sourceUpdatedAt: '2026-10-24T16:00:00Z', returnDate: 'Oct 30', linkReason: 'matched', teamMismatch: false }
  it('preserves source text and formats its update time in dated CT', () => {
    expect(nhlInjuryDetails(injury)).toEqual({ ...injury, updated: { dateTime: injury.sourceUpdatedAt, label: 'Oct 24, 2026, 11:00 AM CT' }, identity: null })
  })
  it.each([null, '', 'not-a-time'])('keeps invalid or missing source update %s unavailable without a fetch substitute', value => {
    expect(nhlContextTime(value)).toBeNull()
    expect(nhlInjuryDetails({ ...injury, sourceUpdatedAt: value }).updated).toBeNull()
  })
  it('distinguishes unresolved identity from source/roster team mismatch', () => {
    expect(nhlInjuryDetails({ ...injury, playerId: null, linkReason: 'no_candidate' }).identity).toBe('Unresolved identity')
    expect(nhlInjuryDetails({ ...injury, playerId: null, linkReason: 'team_mismatch', teamMismatch: true }).identity)
      .toBe('Unresolved identity / Source team differs from roster')
  })
  it('does not invent missing source detail or return date', () => {
    expect(nhlInjuryDetails({ ...injury, detail: null, returnDate: null })).toMatchObject({ detail: null, returnDate: null })
  })
})

describe('NHL context freshness', () => {
  it.each([
    ['2026-10-24T13:00:00Z', 'fresh'],
    ['2026-10-24T12:59:59.999Z', 'stale'],
    ['2026-10-24T19:00:00.001Z', 'unavailable'],
    ['bad-time', 'unavailable'],
    [null, 'unavailable'],
  ] as const)('classifies fetch %s as %s', (fetchedAt, expected) => {
    expect(nhlContextFreshness({ ...source, fetchedAt }, START, NOW)).toBe(expected)
  })
  it('keeps a server stale decision and a server unavailable decision with a known fetch', () => {
    expect(nhlContextFreshness({ ...source, freshness: 'stale' }, START, NOW)).toBe('stale')
    expect(nhlContextSource({ ...source, freshness: 'unavailable' }, START, NOW)).toMatchObject({
      freshness: 'unavailable', fetchedAt: source.fetchedAt, fetchedLabel: 'Oct 24, 2026, 1:00 PM CT',
    })
  })
  it.each([null, 'bad-start', source.fetchedAt])('rejects unknown, invalid or non-pre-start cutoff %s', start => {
    expect(nhlContextFreshness(source, start, NOW)).toBe('unavailable')
  })
  it('ages historical reports at puck drop rather than the current clock', () => {
    expect(nhlContextFreshness(source, START, new Date('2026-11-01T00:00:00Z'))).toBe('fresh')
    expect(nhlContextFreshness({ ...source, fetchedAt: '2026-10-24T17:59:59Z' }, START, new Date('2026-11-01T00:00:00Z'))).toBe('stale')
  })
  it('handles an old API response and invalid clock/time without manufacturing a valid time element', () => {
    expect(nhlContextFreshness(undefined, START, NOW)).toBe('unavailable')
    expect(nhlContextFreshness(source, START, new Date('bad'))).toBe('unavailable')
    expect(nhlContextSource({ ...source, fetchedAt: 'bad' }, START, NOW)).toMatchObject({ fetchedAt: null, fetchedLabel: 'Fetch time unavailable' })
  })
})

describe('NHL goalie and injury slate labels', () => {
  it.each(['expected', 'confirmed'] as const)('retains the source name and %s report for an unresolved identity', status => {
    const side = { ...context().goalies.away, playerName: 'Jean-Francois Long Source Name', status }
    expect(nhlGoalieLabel(side, true)).toEqual({ name: side.playerName, status: status === 'expected' ? 'Expected' : 'Confirmed', unresolved: true })
    expect(nhlGoalieLabel({ ...side, playerId: 4 }, true).unresolved).toBe(false)
  })
  it('keeps an unknown source status without upgrading it to Expected or Confirmed', () => {
    const side = { ...context().goalies.away, playerName: 'Source Name', status: 'unknown' as const, rawStatus: 'Questionable' }
    expect(nhlGoalieLabel(side, true).status).toBe('Unknown status: Questionable')
    expect(nhlGoalieLabel({ ...side, rawStatus: null }, true).status).toBe('Unknown status')
  })
  it('distinguishes no announcement from unavailable, without resurrecting a name', () => {
    const side = { ...context().goalies.away, playerName: 'Older Name', status: 'not_reported' as const }
    expect(nhlGoalieLabel(side, true)).toEqual({ name: null, status: 'Not reported', unresolved: false })
    expect(nhlGoalieLabel(side, false)).toEqual({ name: null, status: 'Unavailable', unresolved: false })
    expect(nhlGoalieLabel({ ...side, status: 'unavailable' }, true).status).toBe('Unavailable')
  })
  it('distinguishes a successful empty report from unknown counts', () => {
    expect(prepare(context()).injuries).toMatchObject({ away: 0, home: 0, empty: true })
    expect(prepare(undefined).injuries).toMatchObject({ away: null, home: null, empty: false })
    expect(prepare(unavailableNhlContext('TBL', 'CHI')).injuries.empty).toBe(false)
  })
  it('counts all reported injuries including unresolved and team-mismatched source identities', () => {
    const value = context()
    const injury: NhlInjury = { espnAthleteId: '1', playerId: null, playerName: 'Source Name', team: 'TBL', status: 'Out', detail: null,
      sourceUpdatedAt: null, returnDate: null, linkReason: 'team_mismatch', teamMismatch: true }
    value.injuries.away = [injury]
    expect(prepare(value).injuries).toMatchObject({ away: 1, home: 0, empty: false })
  })
  it('ages each feed independently and keeps stale named reports and counts visible', () => {
    const value = context()
    value.goalies = { ...value.goalies, fetchedAt: '2026-10-24T12:00:00Z', away: { ...value.goalies.away, playerName: 'Source Name', status: 'expected' } }
    const result = prepare(value)
    expect(result.injuries.freshness).toBe('fresh')
    expect(result.goalies.freshness).toBe('stale')
    expect(result.goalies.away.name).toBe('Source Name')
    value.injuries.freshness = 'unavailable'
    expect(prepare(value).injuries.away).toBeNull()
    expect(prepare(value).goalies.away.name).toBe('Source Name')
  })
  it('creates independent empty arrays and team-labelled missing goalies', () => {
    const a = unavailableNhlContext('LAK', 'NJD')
    const b = unavailableNhlContext('TBL', 'CHI')
    expect(a.injuries.away).not.toBe(a.injuries.home)
    expect(a.injuries.away).not.toBe(b.injuries.away)
    expect(a.goalies.away.team).toBe('LAK')
    expect(a.goalies.home.team).toBe('NJD')
  })
})
