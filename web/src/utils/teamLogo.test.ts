import { describe, expect, it } from 'vitest'
import { isLogoSport, teamLogoUrl } from '~/utils/teamLogo'

const logo = (sport: string, code: string, pixels: number) =>
  `https://a.espncdn.com/combiner/i?img=/i/teamlogos/${sport}/500/${code}.png&w=${pixels}&h=${pixels}`

describe('teamLogoUrl', () => {
  it('lower-cases the stored code on ESPN\'s per-sport path', () => {
    expect(teamLogoUrl('nba', 'GS', 16)).toBe(logo('nba', 'gs', 32))
    expect(teamLogoUrl('nfl', 'KC', 16)).toBe(logo('nfl', 'kc', 32))
    expect(teamLogoUrl('nhl', 'BOS', 16)).toBe(logo('nhl', 'bos', 32))
  })

  it('resizes to twice the display size, for slate rows, home cards and game heroes', () => {
    expect(teamLogoUrl('nba', 'BOS', 16)).toBe(logo('nba', 'bos', 32))
    expect(teamLogoUrl('nba', 'BOS', 14)).toBe(logo('nba', 'bos', 28))
    expect(teamLogoUrl('nba', 'BOS', 52)).toBe(logo('nba', 'bos', 104))
  })

  it('rounds a fractional size to a whole pixel', () => {
    expect(teamLogoUrl('nba', 'BOS', 13.3)).toBe(logo('nba', 'bos', 27))
  })

  it('maps the three NHL codes ESPN spells differently', () => {
    expect(teamLogoUrl('nhl', 'LAK', 52)).toBe(logo('nhl', 'la', 104))
    expect(teamLogoUrl('nhl', 'SJS', 52)).toBe(logo('nhl', 'sj', 104))
    expect(teamLogoUrl('nhl', 'TBL', 52)).toBe(logo('nhl', 'tb', 104))
  })

  it('applies an override only to its own sport', () => {
    expect(teamLogoUrl('nba', 'LAK', 16)).toBe(logo('nba', 'lak', 32))
  })

  it('returns null when there is no code', () => {
    expect(teamLogoUrl('nba', '', 16)).toBeNull()
    expect(teamLogoUrl('nhl', '   ', 52)).toBeNull()
  })
})

describe('isLogoSport', () => {
  it('is true for the three team sports and false for tennis', () => {
    expect(['nba', 'nhl', 'nfl'].every(isLogoSport)).toBe(true)
    expect(isLogoSport('tennis')).toBe(false)
  })
})
