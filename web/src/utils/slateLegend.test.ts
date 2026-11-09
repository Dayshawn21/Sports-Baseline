import { describe, expect, it } from 'vitest'
import { SPORT_STATUS } from '~/pages/howItWorksContent'
import { SLATE_LEGENDS, type SlateLegendContent, tennisLegend } from '~/utils/slateLegend'
import { SPORTS } from '~/utils/sportNav'

function legendText(legend: SlateLegendContent): string[] {
  return [...legend.parts.flatMap(part => [part.label, part.text]), ...legend.pick]
}

describe('SLATE_LEGENDS', () => {
  it.each(SPORTS.map(sport => sport.code))('gives %s at least one part and one pick sentence', code => {
    expect(SLATE_LEGENDS[code].parts.length).toBeGreaterThan(0)
    expect(SLATE_LEGENDS[code].pick.length).toBeGreaterThan(0)
  })

  it('never states a clock time, which the period line owns', () => {
    const text = SPORTS.flatMap(sport => legendText(SLATE_LEGENDS[sport.code]))
    expect(text.filter(line => /\d:\d\d/.test(line))).toEqual([])
  })

  it('opens with "no picks" for every sport How it works lists with none', () => {
    const noPicks = SPORTS.map(sport => sport.code).filter(code => SPORT_STATUS[code].picks === 'None.')
    expect(noPicks).toEqual(['nfl', 'nba', 'nhl'])
    for (const code of noPicks) expect(SLATE_LEGENDS[code].pick[0]).toMatch(/^No .*picks/)
  })

  it('keeps internal plan codes such as "(27j)" out of the copy', () => {
    const text = [...SPORTS.flatMap(sport => legendText(SLATE_LEGENDS[sport.code])), ...legendText(tennisLegend('DraftKings'))]
    expect(text.filter(line => /\(\d+[a-z]\d*\)/.test(line))).toEqual([])
  })

  it('defines the NFL prop gap as model minus line, scaled by a typical line, and as reference only', () => {
    const pick = SLATE_LEGENDS.nfl.pick.join(' ')
    expect(pick).toMatch(/prop gap is the model's projection minus the prop line, as a share of a typical line/)
    expect(pick).toMatch(/Gaps are reference only/)
    expect(pick).toMatch(/Q and D count questionable and doubtful/)
  })

  it('names the NHL book order once, since the slate cells no longer show a book', () => {
    const text = legendText(SLATE_LEGENDS.nhl).join(' ')
    for (const book of ['DraftKings', 'FanDuel', 'bet365']) expect(text.split(book)).toHaveLength(2)
  })
})

describe('tennisLegend', () => {
  it('says EV appears only with a stored book price, never that every pick carries one', () => {
    const pick = tennisLegend('PrizePicks').pick.join(' ')
    expect(pick).not.toMatch(/carry their expected value/)
    expect(pick).toMatch(/expected value only when a book price is stored/)
    expect(pick).toMatch(/Model lean .* gray/)
  })

  it('names the active prop source', () => {
    expect(tennisLegend('DraftKings').parts[0]).toEqual({ label: 'Props', text: 'DraftKings' })
    expect(SLATE_LEGENDS.tennis.parts[0].text).toBe('PrizePicks')
  })
})
