import { describe, expect, it } from 'vitest'
import { toolLabel } from '~/utils/askStatus'

describe('toolLabel', () => {
  it.each([
    ['get_slate', 'nba', 'Checking the NBA slate'],
    ['get_top_props', 'tennis', 'Reading the tennis prop board'],
    ['get_game_detail', 'nfl', 'Opening the NFL game'],
    ['get_game_detail', 'tennis', 'Opening the tennis match'],
    ['get_player', 'nfl', 'Looking up the NFL player'],
    ['get_model_track_record', 'nba', "Reading the NBA model's track record"],
    ['find', 'nba', 'Searching Lineform'],
  ] as const)('%s for %s reads "%s"', (name, sport, expected) => {
    expect(toolLabel(name, sport)).toBe(expected)
  })

  it('leaves the sport out when the tool sent none', () => {
    expect(toolLabel('get_slate', null)).toBe('Checking the slate')
  })

  it('falls back for a tool it does not know', () => {
    expect(toolLabel('get_weather', 'nba')).toBe('Checking Lineform data')
  })
})
