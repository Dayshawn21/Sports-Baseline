import { describe, expect, it } from 'vitest'
import { REFERENCE, agreementTone, barTone, groupAltLines, probabilityRing, statStrip, tennisRowSignal, type RowSignal } from '~/utils/propRowVisuals'

const adoptedOver: RowSignal = { kind: 'adopted', side: 'over' }
const adoptedUnder: RowSignal = { kind: 'adopted', side: 'under' }

describe('agreementTone', () => {
  it('keeps a reference row gray whatever the direction', () => {
    for (const direction of ['over', 'under', 'push', null] as const) {
      expect(agreementTone(REFERENCE, direction)).toBe('neutral')
    }
  })

  it('is positive for the adopted side and negative for the opposite side', () => {
    expect(agreementTone(adoptedOver, 'over')).toBe('positive')
    expect(agreementTone(adoptedOver, 'under')).toBe('negative')
    expect(agreementTone(adoptedUnder, 'under')).toBe('positive')
    expect(agreementTone(adoptedUnder, 'over')).toBe('negative')
  })

  it('stays gray on a push or a missing direction even when adopted', () => {
    expect(agreementTone(adoptedOver, 'push')).toBe('neutral')
    expect(agreementTone(adoptedUnder, null)).toBe('neutral')
  })
})

describe('barTone', () => {
  it('keeps every bar gray on a reference row', () => {
    for (const vsLine of ['above', 'below', 'push', null] as const) {
      expect(barTone(REFERENCE, vsLine)).toBe('neutral')
    }
  })

  it('reads a bar above the line as over and below as under for an adopted row', () => {
    expect(barTone(adoptedOver, 'above')).toBe('positive')
    expect(barTone(adoptedOver, 'below')).toBe('negative')
    expect(barTone(adoptedUnder, 'below')).toBe('positive')
    expect(barTone(adoptedUnder, 'above')).toBe('negative')
  })

  it('leaves a push or an unlined bar gray even when adopted', () => {
    expect(barTone(adoptedOver, 'push')).toBe('neutral')
    expect(barTone(adoptedOver, null)).toBe('neutral')
  })
})

describe('groupAltLines', () => {
  it('keeps the standard rung as main and orders alts by line, then standard, goblin, demon', () => {
    const rungs = [
      { line: 14.5, oddsType: 'demon' },
      { line: 13.5, oddsType: 'standard' },
      { line: 9.5, oddsType: 'goblin' },
      { line: 7.5, oddsType: 'goblin' },
      { line: 9.5, oddsType: 'demon' },
    ]
    const group = groupAltLines(rungs)
    expect(group?.main).toEqual({ line: 13.5, oddsType: 'standard' })
    expect(group?.alts).toEqual([
      { line: 7.5, oddsType: 'goblin' },
      { line: 9.5, oddsType: 'goblin' },
      { line: 9.5, oddsType: 'demon' },
      { line: 14.5, oddsType: 'demon' },
    ])
    expect(group?.count).toBe(4)
  })

  it('falls back to the first rung as main when there is no standard line, as the Line cell does', () => {
    const group = groupAltLines([{ line: 5.5, oddsType: 'demon' }, { line: 2.5, oddsType: 'goblin' }])
    expect(group?.main).toEqual({ line: 5.5, oddsType: 'demon' })
    expect(group?.alts).toEqual([{ line: 2.5, oddsType: 'goblin' }])
  })

  it('carries each rung through unchanged, notes included', () => {
    const group = groupAltLines([{ line: 4.5, oddsType: 'standard' }, { line: 3.5, oddsType: 'goblin', note: '71%' }])
    expect(group?.alts[0].note).toBe('71%')
  })

  it('counts no alts for a single rung', () => {
    expect(groupAltLines([{ line: 4.5, oddsType: 'standard' }])).toEqual({ main: { line: 4.5, oddsType: 'standard' }, alts: [], count: 0 })
  })

  it('returns null when there are no rungs', () => {
    expect(groupAltLines([])).toBeNull()
  })

  it('does not reorder the caller array', () => {
    const rungs = [{ line: 9.5, oddsType: 'demon' }, { line: 4.5, oddsType: 'standard' }, { line: 2.5, oddsType: 'goblin' }]
    groupAltLines(rungs)
    expect(rungs.map(rung => rung.line)).toEqual([9.5, 4.5, 2.5])
  })
})

describe('tennisRowSignal', () => {
  it('is reference unless 48e adopted the line', () => {
    expect(tennisRowSignal({})).toEqual(REFERENCE)
    expect(tennisRowSignal({ adoptedPick: null })).toEqual(REFERENCE)
  })

  it('takes the side from the adopted pick', () => {
    const pick = { side: 'under' as const, probability: 0.6, breakEven: 0.54, margin: 0.06, rule: '48e', projectionVersion: 'props-v3' }
    expect(tennisRowSignal({ adoptedPick: pick })).toEqual({ kind: 'adopted', side: 'under' })
  })
})

describe('probabilityRing', () => {
  it('draws no ring without a probability', () => {
    expect(probabilityRing(null, REFERENCE)).toBeNull()
    expect(probabilityRing(Number.NaN, REFERENCE)).toBeNull()
  })

  it('clamps to 0-100 and stays gray on a reference row', () => {
    expect(probabilityRing(112, REFERENCE)).toEqual({ pct: 100, arcPct: 100, breakEvenPct: null, tone: 'neutral' })
    expect(probabilityRing(-4, REFERENCE)?.pct).toBe(0)
  })

  it('passes the break-even tick through, clamped', () => {
    expect(probabilityRing(62, REFERENCE, 54.2)?.breakEvenPct).toBe(54.2)
    expect(probabilityRing(62, REFERENCE, 130)?.breakEvenPct).toBe(100)
  })

  it('tones only an adopted row, with the arc on the picked side', () => {
    expect(probabilityRing(62, adoptedOver)).toEqual({ pct: 62, arcPct: 62, breakEvenPct: null, tone: 'positive' })
    expect(probabilityRing(38, adoptedUnder)).toEqual({ pct: 38, arcPct: 62, breakEvenPct: null, tone: 'positive' })
  })
})

describe('statStrip', () => {
  const tones = (cells: ReturnType<typeof statStrip>) => cells.map(cell => cell.tone)

  it('gives L5 hits, the average and the diff on five games, without L10', () => {
    expect(statStrip([16, 12, 13.5, 15, 14], 13.5, REFERENCE)).toEqual([
      { key: 'l5', label: 'L5', value: '3/5', tone: 'neutral' },
      { key: 'avg', label: 'Avg', value: '14.1', tone: 'neutral' },
      { key: 'diff', label: 'Diff', value: '+0.6', tone: 'neutral' },
    ])
  })

  it('never counts a push as a hit', () => {
    expect(statStrip([5, 5, 6], 5, REFERENCE)[0]).toMatchObject({ label: 'L3', value: '1/3' })
  })

  it('adds L10 with ten games, and the average and diff use those ten', () => {
    const cells = statStrip([10, 10, 10, 10, 10, 0, 0, 0, 0, 0, 99], 4.5, REFERENCE)
    expect(cells.map(cell => [cell.key, cell.value])).toEqual([['l5', '5/5'], ['l10', '5/10'], ['avg', '5.0'], ['diff', '+0.5']])
  })

  it('omits L10 with fewer than ten games', () => {
    expect(statStrip([3, 4, 5, 6, 7, 8, 9], 5.5, REFERENCE).map(cell => cell.key)).toEqual(['l5', 'avg', 'diff'])
  })

  it('returns no cells without games or without a line', () => {
    expect(statStrip([], 5.5, REFERENCE)).toEqual([])
    expect(statStrip([4, 6], null, REFERENCE)).toEqual([])
  })

  it('prints a negative diff with its sign and no stray minus zero', () => {
    expect(statStrip([10, 11], 12, REFERENCE).at(-1)?.value).toBe('-1.5')
    expect(statStrip([12.04], 12, REFERENCE).at(-1)?.value).toBe('0.0')
  })

  it('keeps every cell gray on a reference row', () => {
    expect(tones(statStrip([20, 20, 20, 20, 20, 20, 20, 20, 20, 20], 5.5, REFERENCE))).toEqual(['neutral', 'neutral', 'neutral', 'neutral'])
  })

  it('tones hit and diff cells against an adopted side, leaving the average gray', () => {
    expect(tones(statStrip([8, 8, 8, 2, 2], 5.5, adoptedOver))).toEqual(['positive', 'neutral', 'positive'])
    expect(tones(statStrip([8, 8, 8, 2, 2], 5.5, adoptedUnder))).toEqual(['negative', 'neutral', 'negative'])
  })
})
