import { describe, expect, it } from 'vitest'
import {
  arrivedFromBoard, FROM_BOARD, injuryTone, latestTime, PAYOUT_TIER_NOTE, payoutTierNote, playerSearch, playerTabs, propSectionIds, selectedMarket,
} from '~/utils/playerPage'

describe('injuryTone', () => {
  it('is plain with no designation', () => {
    expect(injuryTone(null)).toBe('default')
    expect(injuryTone(' ')).toBe('default')
  })

  it('marks Out strongest, in any case', () => {
    expect(injuryTone('Out')).toBe('out')
    expect(injuryTone(' OUT ')).toBe('out')
  })

  it('treats every other designation as a caution', () => {
    expect(injuryTone('Questionable')).toBe('caution')
    expect(injuryTone('Day-To-Day')).toBe('caution')
  })
})

describe('latestTime', () => {
  it('returns the newest parseable timestamp', () => {
    expect(latestTime(['2026-11-09T17:00:00Z', null, '2026-11-09T23:31:00Z', 'not a time', '2026-11-08T12:00:00Z'])).toBe('2026-11-09T23:31:00Z')
  })

  it('is null when nothing parses', () => {
    expect(latestTime([])).toBeNull()
    expect(latestTime([null, 'bad'])).toBeNull()
  })
})

describe('payoutTierNote', () => {
  it('explains the tiers when any line is a goblin or demon, in any case', () => {
    expect(payoutTierNote(['Standard', 'Goblin'])).toBe(PAYOUT_TIER_NOTE)
    expect(payoutTierNote(['demon'])).toBe(PAYOUT_TIER_NOTE)
    expect(payoutTierNote([' DEMON '])).toBe(PAYOUT_TIER_NOTE)
  })

  it('is null for standard-only or other line types', () => {
    expect(payoutTierNote([])).toBeNull()
    expect(payoutTierNote(['Standard', 'PrizePicks', 'goblins'])).toBeNull()
  })
})

describe('propSectionIds', () => {
  it('names a section per market and numbers a repeat', () => {
    expect(propSectionIds(['receiving_yards', 'receptions', 'receiving_yards'])).toEqual(['prop-receiving_yards', 'prop-receptions', 'prop-receiving_yards-2'])
  })

  it('is empty for no markets', () => {
    expect(propSectionIds([])).toEqual([])
  })
})

describe('playerSearch', () => {
  it('changes one param and keeps the rest', () => {
    const params = new URLSearchParams('market=receptions&form=opp')
    expect(playerSearch(params, { market: 'receiving_yards' })).toBe('?market=receiving_yards&form=opp')
    expect(playerSearch(params, { form: '10' })).toBe('?market=receptions&form=10')
  })

  it('removes a param set to null and encodes values', () => {
    expect(playerSearch(new URLSearchParams('market=receptions&form=opp'), { form: null })).toBe('?market=receptions')
    expect(playerSearch(new URLSearchParams(''), { market: 'a b' })).toBe('?market=a+b')
    expect(playerSearch(new URLSearchParams('form=10'), { form: null })).toBe('?')
  })
})

describe('arrivedFromBoard', () => {
  it('is true only for the state a board row sets', () => {
    expect(arrivedFromBoard(FROM_BOARD)).toBe(true)
    expect([arrivedFromBoard(null), arrivedFromBoard(undefined), arrivedFromBoard({}), arrivedFromBoard({ from: 'game' }), arrivedFromBoard('board')]).toEqual([false, false, false, false, false])
  })
})

describe('playerTabs and selectedMarket', () => {
  const tabs = playerTabs([{ market: 'points' }, { market: 'assists' }, { market: 'points' }])

  it('keeps the API order and lists a market once', () => {
    expect(tabs).toEqual(['points', 'assists'])
  })

  it('selects the asked market, else the first, else none', () => {
    expect(selectedMarket(new URLSearchParams('market=assists'), tabs)).toBe('assists')
    expect(selectedMarket(new URLSearchParams('market=hits'), tabs)).toBe('points')
    expect(selectedMarket(new URLSearchParams(''), tabs)).toBe('points')
    expect(selectedMarket(new URLSearchParams('market=points'), [])).toBeNull()
  })
})
