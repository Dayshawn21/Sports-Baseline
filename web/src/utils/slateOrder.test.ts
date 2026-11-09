import { describe, expect, it } from 'vitest'
import { finalsStartOpen, isResultPending, openWindowTitle, orderByPhase, type SlatePhase, slatePhase, orderWindowsByPhase, splitFinals } from '~/utils/slateOrder'

interface Game { id: string, phase: SlatePhase }
interface Window { key: string, games: Game[] }

const g = (id: string, phase: SlatePhase): Game => ({ id, phase })
const phaseOf = (game: Game) => game.phase
const ids = (games: readonly Game[]) => games.map(game => game.id)
const keys = (windows: readonly Window[]) => windows.map(window => window.key)

describe('slatePhase', () => {
  it('reads a started game as live and keeps the rest', () => {
    expect(slatePhase('started')).toBe('live')
    expect(slatePhase('live')).toBe('live')
    expect(slatePhase('off')).toBe('off')
    expect(slatePhase('final')).toBe('final')
  })

  it('sorts a game whose result is pending with the finals', () => {
    expect(slatePhase('pending')).toBe('final')
  })
})

describe('isResultPending', () => {
  const SNF = '2026-11-09T01:20:00Z'

  it('is true only once a game is over five hours past its start', () => {
    expect(isResultPending(SNF, new Date('2026-11-09T04:20:00Z'))).toBe(false)
    expect(isResultPending(SNF, new Date('2026-11-09T06:20:00Z'))).toBe(false)
    expect(isResultPending(SNF, new Date('2026-11-09T06:21:00Z'))).toBe(true)
    expect(isResultPending(SNF, new Date('2026-11-09T14:20:00Z'))).toBe(true)
  })

  it('is false without a parseable start', () => {
    expect(isResultPending(null, new Date('2026-11-09T14:20:00Z'))).toBe(false)
    expect(isResultPending('not a time', new Date('2026-11-09T14:20:00Z'))).toBe(false)
  })
})

describe('a Monday morning slate', () => {
  it('moves a Sunday night game with no score out of the lead and in with the finals', () => {
    const states = { thu: 'final', snf: 'pending', mnf: 'upcoming' } as const
    const games = [g('thu', slatePhase(states.thu)), g('snf', slatePhase(states.snf)), g('mnf', slatePhase(states.mnf))]
    const { open, finals } = splitFinals(games, phaseOf)
    expect([ids(open), ids(finals)]).toEqual([['mnf'], ['thu', 'snf']])
  })
})

describe('orderByPhase', () => {
  it('puts live, upcoming, off, final in that order and keeps order within a phase', () => {
    const games = [g('f1', 'final'), g('u1', 'upcoming'), g('o1', 'off'), g('l1', 'live'), g('u2', 'upcoming'), g('l2', 'live')]
    expect(ids(orderByPhase(games, phaseOf))).toEqual(['l1', 'l2', 'u1', 'u2', 'o1', 'f1'])
  })

  it('does not mutate its input', () => {
    const games = [g('f1', 'final'), g('l1', 'live')]
    orderByPhase(games, phaseOf)
    expect(ids(games)).toEqual(['f1', 'l1'])
  })
})

describe('splitFinals', () => {
  it('lifts finals out in their own order', () => {
    const { open, finals } = splitFinals([g('f2', 'final'), g('u1', 'upcoming'), g('f1', 'final'), g('l1', 'live')], phaseOf)
    expect(ids(open)).toEqual(['l1', 'u1'])
    expect(ids(finals)).toEqual(['f2', 'f1'])
  })
})

describe('orderWindowsByPhase', () => {
  // A Sunday night after finals were lifted out: the late window keeps one live game, SNF is live, MNF to come.
  const sunday: Window[] = [
    { key: 'late', games: [g('t2', 'live')] },
    { key: 'thu', games: [g('thu', 'upcoming')] },
    { key: 'prime', games: [g('snf', 'live'), g('mnf', 'upcoming')] },
    { key: 'none', games: [g('x', 'upcoming')] },
  ]

  it('leads with windows that hold a live game, then the rest in their given order', () => {
    expect(keys(orderWindowsByPhase(sunday, phaseOf))).toEqual(['late', 'prime', 'thu', 'none'])
  })

  it('keeps kickoff order when nothing is live', () => {
    const quiet = [{ key: 'thu', games: [g('thu', 'upcoming')] }, { key: 'sun', games: [g('sun', 'upcoming')] }]
    expect(keys(orderWindowsByPhase(quiet, phaseOf))).toEqual(['thu', 'sun'])
  })

  it('leaves the games inside each window untouched', () => {
    expect(ids(orderWindowsByPhase(sunday, phaseOf)[1].games)).toEqual(['snf', 'mnf'])
  })
})

describe('finalsStartOpen', () => {
  it('opens only for an all-final slate or a search', () => {
    expect(finalsStartOpen(3, false)).toBe(false)
    expect(finalsStartOpen(0, false)).toBe(true)
    expect(finalsStartOpen(3, true)).toBe(true)
  })
})

describe('openWindowTitle', () => {
  it('says what is left once a game is final', () => {
    expect(openWindowTitle(0)).toBe('All games')
    expect(openWindowTitle(2)).toBe('Still to play')
  })
})
