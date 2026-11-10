import { describe, expect, it } from 'vitest'
import { isLogoSport, teamLogoUrl } from '~/utils/teamLogo'

describe('teamLogoUrl', () => {
  it('lower-cases the stored code on ESPN\'s per-sport path', () => {
    expect(teamLogoUrl('nba', 'GS')).toBe('https://a.espncdn.com/i/teamlogos/nba/500/gs.png')
    expect(teamLogoUrl('nfl', 'KC')).toBe('https://a.espncdn.com/i/teamlogos/nfl/500/kc.png')
    expect(teamLogoUrl('nhl', 'BOS')).toBe('https://a.espncdn.com/i/teamlogos/nhl/500/bos.png')
  })

  it('maps the three NHL codes ESPN spells differently', () => {
    expect(teamLogoUrl('nhl', 'LAK')).toBe('https://a.espncdn.com/i/teamlogos/nhl/500/la.png')
    expect(teamLogoUrl('nhl', 'SJS')).toBe('https://a.espncdn.com/i/teamlogos/nhl/500/sj.png')
    expect(teamLogoUrl('nhl', 'TBL')).toBe('https://a.espncdn.com/i/teamlogos/nhl/500/tb.png')
  })

  it('applies an override only to its own sport', () => {
    expect(teamLogoUrl('nba', 'LAK')).toBe('https://a.espncdn.com/i/teamlogos/nba/500/lak.png')
  })

  it('returns null when there is no code', () => {
    expect(teamLogoUrl('nba', '')).toBeNull()
    expect(teamLogoUrl('nhl', '   ')).toBeNull()
  })
})

describe('isLogoSport', () => {
  it('is true for the three team sports and false for tennis', () => {
    expect(['nba', 'nhl', 'nfl'].every(isLogoSport)).toBe(true)
    expect(isLogoSport('tennis')).toBe(false)
  })
})
