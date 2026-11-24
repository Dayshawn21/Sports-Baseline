import { describe, expect, it } from 'vitest'
import { splitByTour } from '~/utils/bankrollTours'

const single = (id: string, tour: string) => ({ id, tour })
const parlay = (id: string, ...tours: string[]) => ({ id, legs: tours.map((tour) => ({ tour })) })

describe('splitByTour', () => {
  it('puts ATP and WTA singles in the main section, case-insensitively', () => {
    const split = splitByTour({
      singles: [single('a', 'ATP'), single('b', 'wta'), single('c', 'CHALLENGER'), single('d', 'ITF')],
      parlays: [],
    })
    expect(split.mainSingles.map((s) => s.id)).toEqual(['a', 'b'])
    expect(split.challSingles.map((s) => s.id)).toEqual(['c', 'd'])
  })

  it('sends a parlay with any non-main leg to the Challenger section', () => {
    const split = splitByTour({
      singles: [],
      parlays: [parlay('main', 'ATP', 'Wta'), parlay('mixed', 'ATP', 'CHALLENGER'), parlay('chall', 'CHALLENGER')],
    })
    expect(split.mainParlays.map((p) => p.id)).toEqual(['main'])
    expect(split.challParlays.map((p) => p.id)).toEqual(['mixed', 'chall'])
  })

  it('returns empty lists for an empty slate', () => {
    expect(splitByTour({ singles: [], parlays: [] })).toEqual({
      mainSingles: [], challSingles: [], mainParlays: [], challParlays: [],
    })
  })
})
