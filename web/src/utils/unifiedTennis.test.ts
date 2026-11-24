import { describe, expect, it } from 'vitest'
import type { BankrollPick, BestPick, MatchBestPicks, MatchPrediction, PropLine } from '~/types/tennis'
import {
  assessPropsHealth,
  anglePicks,
  bestBetPicks,
  composeUnifiedMatches,
  displayedBestPicks,
  normalizeName,
  sortUnifiedMatches,
} from '~/utils/unifiedTennis'
import type { UnifiedSort } from '~/utils/unifiedTennis'

// 2026-08-24T18:00:00Z == 1:00 PM America/Chicago
const NOW = Date.parse('2026-08-24T18:00:00Z')
const SOON = '2026-08-24T20:00:00Z'
const CT_DATE = '2026-08-24'

const BASE_FILTERS = { showLeans: false, upcomingOnly: false, now: NOW }

function prediction(over: Partial<MatchPrediction> = {}): MatchPrediction {
  return {
    matchId: 1,
    startUtc: SOON,
    p1Name: 'Jannik Sinner',
    p2Name: 'Carlos Alcaraz',
    tour: 'ATP',
    surface: 'Hard',
    tournament: 'US Open',
    round: 'QF',
    p1WinProb: 0.64,
    p2WinProb: 0.36,
    p1EloProb: 0.61,
    p1MlProb: 0.66,
    p1MarketProb: 0.58,
    ensembleWeights: {},
    qualityFlags: [],
    p1OddsAmerican: -150,
    p2OddsAmerican: 130,
    h2hP1Wins: 3,
    h2hP2Wins: 2,
    ...over,
  }
}

function pick(over: Partial<BestPick> = {}): BestPick {
  return {
    pickType: 'moneyline',
    label: 'Moneyline',
    pick: 'Sinner ML (-150)',
    playerName: 'Jannik Sinner',
    edgePct: 10,
    confidence: 'STRONG',
    reasoning: 'model over market',
    oddsAmerican: -150,
    ...over,
  }
}

/** A best pick that clears the priced best-bet bar at its tier. */
function priced(over: Partial<BestPick> = {}): BestPick {
  return pick({ confidence: 'STRONG', evPct: 12, kellyFraction: 0.05, ...over })
}

function bestMatch(over: Partial<MatchBestPicks> = {}): MatchBestPicks {
  return {
    matchId: 1,
    startUtc: SOON,
    p1Name: 'Jannik Sinner',
    p2Name: 'Carlos Alcaraz',
    tour: 'ATP',
    surface: 'Hard',
    tournament: 'US Open',
    round: 'QF',
    p1WinProb: 0.64,
    p2WinProb: 0.36,
    p1OddsAmerican: -150,
    p2OddsAmerican: 130,
    h2hP1Wins: 3,
    h2hP2Wins: 2,
    picks: [pick()],
    ...over,
  }
}

function prop(over: Partial<PropLine> = {}): PropLine {
  return {
    id: 1,
    playerId: 10,
    playerName: 'Jannik Sinner',
    matchId: 1,
    source: 'prizepicks',
    statType: 'Aces',
    line: '8.5',
    oddsType: 'standard',
    fetchedAt: SOON,
    startTime: SOON,
    pOver: 0.6,
    pUnder: 0.4,
    confidence: null,
    recommendation: 'OVER',
    statAvg: 9.4,
    edgePct: 12,
    ...over,
  }
}

function bankrollPick(over: Partial<BankrollPick> = {}): BankrollPick {
  return {
    matchId: 1,
    p1Name: 'Jannik Sinner',
    p2Name: 'Carlos Alcaraz',
    tour: 'ATP',
    surface: 'Hard',
    tournament: 'US Open',
    round: 'QF',
    startUtc: SOON,
    betType: 'underdog_set',
    pickLabel: 'Alcaraz +1.5 Sets (-120)',
    pickSide: 'p2',
    ourProb: 0.66,
    marketProb: 0.55,
    oddsAmerican: -120,
    edgePct: 20,
    ev: 0.12,
    kellyFraction: 0.04,
    confidence: 'STRONG',
    reasoning: 'Alcaraz has a priced set-cover edge',
    ...over,
  }
}

describe('composeUnifiedMatches', () => {
  it('composes a prediction, best pick and prop with the same matchId into one card', () => {
    const result = composeUnifiedMatches([prediction()], [bestMatch()], [prop()], BASE_FILTERS)

    expect(result).toHaveLength(1)
    expect(result[0].matchId).toBe(1)
    expect(result[0].prediction).not.toBeNull()
    expect(result[0].bestPicks).toHaveLength(1)
    expect(result[0].props).toHaveLength(1)
    expect(result[0].inferredPropLink).toBe(false)
  })

  it('shows every rateable prop in board order, whatever its EV or the leans toggle (48f)', () => {
    const props = [
      prop({ id: 1, statType: 'Fantasy Score', oddsType: 'goblin', edgePct: 441, evPct: 6 }),
      prop({ id: 2, statType: 'Aces', evPct: -12 }),
      prop({ id: 3, statType: 'Double Faults', evPct: 38, confidence: 'LOCK' }),
      prop({ id: 4, statType: 'Total Games', evPct: null }),
    ]
    const hidden = composeUnifiedMatches([prediction()], [], props, BASE_FILTERS)
    const shown = composeUnifiedMatches([prediction()], [], props, { ...BASE_FILTERS, showLeans: true })

    expect(hidden[0].props.map((p) => p.statType)).toEqual(['Aces', 'Double Faults', 'Fantasy Score', 'Total Games'])
    expect(shown[0].props.map((p) => p.id)).toEqual(hidden[0].props.map((p) => p.id))
  })

  it('leaves out props the board would not rate', () => {
    const props = [
      prop({ id: 1, statType: 'Aces' }),
      prop({ id: 2, statType: 'Double Faults', recommendation: null }),
      prop({ id: 3, statType: 'Games Won', dataQualityFlags: ['small_sample'] }),
      prop({ id: 4, statType: 'Total Games', pOver: null }),
    ]
    const result = composeUnifiedMatches([prediction()], [], props, BASE_FILTERS)
    expect(result[0].props.map((p) => p.id)).toEqual([1])
  })

  it('keeps a best pick that has no qualifying prop', () => {
    const result = composeUnifiedMatches([prediction()], [bestMatch()], [], BASE_FILTERS)
    expect(result).toHaveLength(1)
    expect(result[0].bestPicks).toHaveLength(1)
  })

  it('adds bankroll singles to the matching card', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [],
      [],
      BASE_FILTERS,
      [bankrollPick()],
    )

    expect(result).toHaveLength(1)
    expect(result[0].bestPicks.map((p) => p.pick)).toEqual(['Alcaraz +1.5 Sets (-120)'])
    expect(result[0].bestPicks[0]).toMatchObject({
      pickType: 'bankroll',
      label: 'Win a Set',
      playerName: 'Carlos Alcaraz',
      oddsAmerican: -120,
      evPct: 12,
    })
  })

  it('shows one moneyline pick when best picks and the bankroll builder both price it', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [bestMatch({ picks: [pick({ evPct: 12, kellyFraction: 0.04 })] })],
      [],
      BASE_FILTERS,
      [bankrollPick({ betType: 'ml', pickLabel: 'Sinner ML (-150)', pickSide: 'p1', oddsAmerican: -150 })],
    )

    const moneylines = result[0].bestPicks.filter((p) => p.label === 'Moneyline')
    expect(moneylines).toHaveLength(1)
    expect(moneylines[0].pickType).toBe('moneyline')
  })

  it('uses a priced bankroll pick instead of an overlapping unpriced derived pick', () => {
    const derivedSetPick = bestMatch({
      picks: [pick({
        pickType: 'derived',
        label: 'Win a Set',
        pick: 'Alcaraz wins a set',
        playerName: 'Carlos Alcaraz',
        evPct: null,
      })],
    })

    const result = composeUnifiedMatches(
      [prediction()],
      [derivedSetPick],
      [],
      BASE_FILTERS,
      [bankrollPick()],
    )

    expect(result[0].bestPicks.map((p) => p.pick)).toEqual(['Alcaraz +1.5 Sets (-120)'])
  })

  it('shows lean bankroll singles only when leans are enabled and EV gates pass', () => {
    const hidden = composeUnifiedMatches(
      [prediction()],
      [],
      [],
      BASE_FILTERS,
      [bankrollPick({ confidence: 'LEAN' })],
    )
    const result = composeUnifiedMatches(
      [prediction()],
      [],
      [],
      { ...BASE_FILTERS, showLeans: true },
      [bankrollPick({ confidence: 'LEAN' })],
    )

    expect(hidden).toEqual([])
    expect(result).toHaveLength(1)
    expect(result[0].bestPicks[0].confidence).toBe('LEAN')
  })

  it('does not show bankroll singles below the card EV threshold', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [],
      [],
      BASE_FILTERS,
      [bankrollPick({ ev: 0.049, kellyFraction: 0.04 })],
    )

    expect(result).toEqual([])
  })

  it('separates priced Best Bets from unpriced Angles', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [bestMatch({
        picks: [
          pick({
            pickType: 'moneyline',
            confidence: 'STRONG',
            evPct: 12,
            kellyFraction: 0.03,
            oddsAmerican: 120,
          }),
          pick({
            pickType: 'derived',
            label: 'Win a Set',
            pick: 'Alcaraz wins a set',
            playerName: 'Carlos Alcaraz',
            evPct: null,
            kellyFraction: null,
            oddsAmerican: null,
            oddsSource: 'unpriced',
          }),
        ],
      })],
      [],
      BASE_FILTERS,
    )

    expect(bestBetPicks(result[0]).map((item) => item.pickType)).toEqual(['moneyline'])
    expect(anglePicks(result[0]).map((item) => item.pickType)).toEqual(['derived'])
  })

  it('hides priced best picks below five percent EV', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [bestMatch({
        picks: [
          pick({
            pickType: 'moneyline',
            confidence: 'LEAN',
            evPct: 4.9,
            kellyFraction: 0.04,
            oddsAmerican: 100,
          }),
        ],
      })],
      [],
      { ...BASE_FILTERS, showLeans: true },
    )

    expect(result).toEqual([])
  })

  it('does not show bankroll singles below the card Kelly threshold', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [],
      [],
      BASE_FILTERS,
      [bankrollPick({ ev: 0.12, kellyFraction: 0.019 })],
    )

    expect(result).toEqual([])
  })

  it('hides games-won overs that cannot win with the visible 2-0 anchor', () => {
    const straightSets = bestMatch({
      picks: [pick({
        pickType: 'derived',
        label: 'Set Score 2-0',
        pick: 'Sinner wins 2-0',
        playerName: 'Jannik Sinner',
      })],
    })
    const props = [
      prop({ id: 1, playerName: 'JANNIK  SINNER', statType: 'Total Games Won', line: '14.5' }),
      prop({ id: 2, statType: 'games_won', line: '14.0' }),
      prop({ id: 3, statType: 'Total Games Won', line: '13.5' }),
      prop({ id: 4, statType: 'Total Games Won', line: '14.5', recommendation: 'UNDER' }),
      prop({ id: 5, statType: 'Aces', line: '14.5' }),
    ]

    const result = composeUnifiedMatches([prediction()], [straightSets], props, BASE_FILTERS)

    expect(result[0].props.map((item) => item.id).sort()).toEqual([3, 4, 5])
  })

  it('keeps a high games-won over when there is no visible 2-0 anchor', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [bestMatch()],
      [prop({ statType: 'Total Games Won', line: '14.5' })],
      BASE_FILTERS,
    )

    expect(result[0].props).toHaveLength(1)
  })

  it('keeps a market prop best pick when the straight-sets filter empties the prop rows', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [bestMatch({
        picks: [
          pick({ pickType: 'derived', label: 'Set Score 2-0', pick: 'Sinner wins 2-0' }),
          pick({ pickType: 'prop', label: 'Total Games', pick: 'Total Games UNDER 22.5' }),
        ],
      })],
      [prop({ statType: 'Total Games Won', line: '14.5' })],
      BASE_FILTERS,
    )

    expect(result[0].props).toEqual([])
    // PrizePicks lines are never best picks (48f), so a prop pick is a book line, not a copy of the row.
    expect(displayedBestPicks(result[0]).map((item) => item.pickType)).toEqual(['derived', 'prop'])
  })

  it('drops a plain prediction with neither a best pick nor a qualifying prop', () => {
    const result = composeUnifiedMatches(
      [prediction()],
      [],
      [prop({ recommendation: null })],
      BASE_FILTERS,
    )
    expect(result).toEqual([])
  })

  it('recovers a prop with a null matchId via the player-name fallback', () => {
    const orphan = prop({ matchId: null, playerName: 'Jannik  SINNER' })
    const result = composeUnifiedMatches([prediction()], [], [orphan], BASE_FILTERS)

    expect(result).toHaveLength(1)
    expect(result[0].matchId).toBe(1)
    expect(result[0].props).toHaveLength(1)
    expect(result[0].inferredPropLink).toBe(true)
  })

  it('matches names across diacritics and punctuation', () => {
    const pred = prediction({ p1Name: 'Félix Auger-Aliassime' })
    const orphan = prop({ matchId: null, playerName: 'Felix Auger Aliassime' })
    const result = composeUnifiedMatches([pred], [], [orphan], BASE_FILTERS)

    expect(result[0].props).toHaveLength(1)
    expect(result[0].inferredPropLink).toBe(true)
  })

  it('emits a prop-only card when no match can be found at all', () => {
    const orphan = prop({ matchId: null, playerName: 'Nobody Here' })
    const result = composeUnifiedMatches([], [], [orphan], BASE_FILTERS)

    expect(result).toHaveLength(1)
    expect(result[0].matchId).toBeNull()
    expect(result[0].prediction).toBeNull()
    expect(result[0].props).toHaveLength(1)
    expect(result[0].key).toContain('nobody here')
  })

  it('keeps demon and goblin variants on the same line distinct', () => {
    const props = [
      prop({ id: 1, oddsType: 'demon' }),
      prop({ id: 2, oddsType: 'goblin' }),
      prop({ id: 3, oddsType: 'goblin' }), // a true duplicate, must collapse
    ]
    const result = composeUnifiedMatches([prediction()], [], props, BASE_FILTERS)
    expect(result[0].props.map((p) => p.oddsType)).toEqual(['demon', 'goblin'])
  })

  it('applies tour, date and upcoming-only filters', () => {
    const atp = prediction({ matchId: 1 })
    const wta = prediction({ matchId: 2, tour: 'WTA', p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' })
    const picks = [bestMatch({ matchId: 1 }), bestMatch({ matchId: 2 })]

    const byTour = composeUnifiedMatches([atp, wta], picks, [], { ...BASE_FILTERS, tour: 'WTA' })
    expect(byTour.map((m) => m.matchId)).toEqual([2])

    const byDate = composeUnifiedMatches([atp, wta], picks, [], { ...BASE_FILTERS, date: CT_DATE })
    expect(byDate).toHaveLength(2)

    const otherDate = composeUnifiedMatches([atp, wta], picks, [], { ...BASE_FILTERS, date: '2026-01-01' })
    expect(otherDate).toEqual([])
  })

  it('drops matches that already started beyond the upcoming buffer', () => {
    const stale = prediction({ startUtc: '2026-08-24T10:00:00Z' }) // 8h before NOW
    const result = composeUnifiedMatches([stale], [bestMatch({ startUtc: '2026-08-24T10:00:00Z' })], [], {
      ...BASE_FILTERS,
      upcomingOnly: true,
    })
    expect(result).toEqual([])
  })

  it('ranks a single high-EV match above one holding more, weaker LOCKs', () => {
    // Three picks barely over the LOCK threshold are worth less than one at +40%.
    // The old count-first sort put the three-LOCK match on top.
    const many = bestMatch({ matchId: 1, picks: [15.1, 15.2, 15.3].map((evPct) => priced({ confidence: 'LOCK', pick: `Pick ${evPct}`, evPct })) })
    const one = bestMatch({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek', picks: [priced({ confidence: 'LOCK', pick: 'Gauff ML', evPct: 40 })] })
    const result = composeUnifiedMatches(
      [prediction({ matchId: 1 }), prediction({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' })],
      [many, one],
      [],
      BASE_FILTERS,
    )
    expect(result.map((m) => m.matchId)).toEqual([2, 1])
  })

  it('uses depth as a tiebreak when top EV is equal', () => {
    const deep = bestMatch({ matchId: 1, picks: [priced({ pick: 'A', evPct: 20 }), priced({ pick: 'B', evPct: 18 })] })
    const shallow = bestMatch({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek', picks: [priced({ pick: 'C', evPct: 20 })] })
    const result = composeUnifiedMatches(
      [prediction({ matchId: 1 }), prediction({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' })],
      [shallow, deep],
      [],
      BASE_FILTERS,
    )
    expect(result.map((m) => m.matchId)).toEqual([1, 2])
  })

  it('never lets PrizePicks props move a card, whatever their EV or tier (48f)', () => {
    const preds = [
      prediction({ matchId: 1, startUtc: '2026-08-24T19:00:00Z' }),
      prediction({ matchId: 2, startUtc: '2026-08-24T20:00:00Z', p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' }),
    ]
    const props = [
      prop({ id: 1, matchId: 2, playerName: 'Coco Gauff', confidence: 'LOCK', evPct: 90 }),
      prop({ id: 2, matchId: 2, playerName: 'Coco Gauff', statType: 'Double Faults', evPct: 80 }),
    ]
    for (const sort of ['opportunity', 'ev', 'confidence', 'items'] as const) {
      expect(composeUnifiedMatches(preds, [], props.concat(prop({ id: 3, matchId: 1 })), { ...BASE_FILTERS, sort }).map((m) => m.matchId)).toEqual([1, 2])
    }
  })

  it('sorts matches with no priced item after priced ones', () => {
    const unpriced = bestMatch({ matchId: 1, picks: [pick({ confidence: 'LOCK', evPct: null })] })
    const priced = bestMatch({
      matchId: 2,
      p1Name: 'Coco Gauff',
      p2Name: 'Iga Swiatek',
      picks: [pick({ confidence: 'STRONG', pick: 'Gauff ML', evPct: 12, kellyFraction: 0.02 })],
    })
    const result = composeUnifiedMatches(
      [prediction({ matchId: 1 }), prediction({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' })],
      [unpriced, priced],
      [],
      BASE_FILTERS,
    )
    expect(result.map((m) => m.matchId)).toEqual([2, 1])
  })

  it('does not reorder the page when LEANs are revealed', () => {
    // Item counts used to drive the sort, so a match padded with LEANs jumped
    // the queue the moment the toggle was flipped.
    const one = bestMatch({ matchId: 1, picks: [priced({ pick: 'A', evPct: 25 })] })
    const two = bestMatch({
      matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek',
      picks: [priced({ pick: 'B', evPct: 10 }), priced({ pick: 'C', confidence: 'LEAN', evPct: 6 }), priced({ pick: 'D', confidence: 'LEAN', evPct: 5.5 })],
    })
    const preds = [
      prediction({ matchId: 1 }),
      prediction({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' }),
    ]
    const hidden = composeUnifiedMatches(preds, [one, two], [], BASE_FILTERS)
    const shown = composeUnifiedMatches(preds, [one, two], [], { ...BASE_FILTERS, showLeans: true })

    expect(hidden.map((m) => m.matchId)).toEqual([1, 2])
    expect(shown.map((m) => m.matchId)).toEqual([1, 2])
  })

  it('ranks unpriced matches by their best confidence tier', () => {
    const one = bestMatch({ matchId: 1, picks: [pick({ confidence: 'STRONG' })] })
    const two = bestMatch({
      matchId: 2,
      p1Name: 'Coco Gauff',
      p2Name: 'Iga Swiatek',
      picks: [pick({ confidence: 'LOCK', pick: 'Gauff ML' })],
    })
    const result = composeUnifiedMatches(
      [prediction({ matchId: 1 }), prediction({ matchId: 2, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' })],
      [one, two],
      [],
      BASE_FILTERS,
    )
    expect(result.map((m) => m.matchId)).toEqual([2, 1])
  })
})

describe('displayedBestPicks', () => {
  it('keeps book-priced prop picks beside PrizePicks rows, since those rows are never picks (48f)', () => {
    const withProps = composeUnifiedMatches(
      [prediction()],
      [bestMatch({ picks: [pick(), pick({ pickType: 'prop', pick: 'OVER 8.5' })] })],
      [prop()],
      BASE_FILTERS,
    )
    expect(displayedBestPicks(withProps[0]).map((p) => p.pickType)).toEqual(['moneyline', 'prop'])
  })

  it('keeps prop-type best picks when there are no prop rows', () => {
    const withoutProps = composeUnifiedMatches(
      [prediction()],
      [bestMatch({ picks: [pick(), pick({ pickType: 'prop', pick: 'OVER 8.5' })] })],
      [],
      BASE_FILTERS,
    )
    expect(displayedBestPicks(withoutProps[0])).toHaveLength(2)
  })
})

describe('assessPropsHealth', () => {
  it('reports healthy when props are linked and scored', () => {
    const health = assessPropsHealth([prop(), prop({ id: 2 })])
    expect(health.degraded).toBe(false)
    expect(health.reason).toBe('none')
  })

  it('flags an unlinked pipeline break rather than an empty slate', () => {
    const broken = Array.from({ length: 10 }, (_, i) =>
      prop({ id: i, matchId: null, recommendation: null, projectionStatus: 'missing_match' }))
    const health = assessPropsHealth(broken)
    expect(health).toMatchObject({ total: 10, linked: 0, scored: 0, degraded: true, reason: 'unlinked' })
  })

  it('flags a source whose markets the model cannot score', () => {
    const spreads = Array.from({ length: 10 }, (_, i) =>
      prop({ id: i, statType: 'game_spread', recommendation: null, projectionStatus: 'unsupported_stat' }))
    const health = assessPropsHealth(spreads)
    expect(health).toMatchObject({ degraded: true, reason: 'unsupported', linked: 10 })
  })

  it('is not degraded when nothing loaded', () => {
    expect(assessPropsHealth([]).degraded).toBe(false)
  })
})

describe('sort modes', () => {
  const LATE = '2026-08-24T21:00:00Z'
  const EARLY = '2026-08-24T13:00:00Z'

  // Match 1 starts later but carries the single best EV; match 2 starts earlier
  // and holds more, weaker picks, so every sort key disagrees with another.
  const predictions = [
    prediction({ matchId: 1, startUtc: LATE }),
    prediction({ matchId: 2, startUtc: EARLY, p1Name: 'Coco Gauff', p2Name: 'Iga Swiatek' }),
  ]
  const bests = [
    bestMatch({ matchId: 1, startUtc: LATE, picks: [priced({ confidence: 'LOCK', pick: 'A', evPct: 40 })] }),
    bestMatch({ matchId: 2, startUtc: EARLY, picks: [priced({ pick: 'B', evPct: 12 }), priced({ pick: 'C', evPct: 11 })] }),
  ]
  const props: PropLine[] = []

  function order(sort?: UnifiedSort): Array<number | null> {
    return composeUnifiedMatches(predictions, bests, props, { ...BASE_FILTERS, sort })
      .map((match) => match.matchId)
  }

  it('defaults to opportunity quality', () => {
    expect(order()).toEqual([1, 2])
    expect(order('opportunity')).toEqual([1, 2])
  })

  it('orders by start time in both directions', () => {
    expect(order('start')).toEqual([2, 1])
    expect(order('start_desc')).toEqual([1, 2])
  })

  it('orders by best single EV and by confidence tier', () => {
    expect(order('ev')).toEqual([1, 2])
    expect(order('confidence')).toEqual([1, 2])
  })

  it('orders by pick count only when asked', () => {
    expect(order('items')).toEqual([2, 1])
  })

  it('breaks ties on a coarse key with opportunity quality', () => {
    // Both matches sit in the same confidence tier, so the higher-EV card must still lead.
    const tied = [
      bestMatch({ matchId: 1, startUtc: LATE, picks: [priced({ pick: 'A', evPct: 40 })] }),
      bestMatch({ matchId: 2, startUtc: EARLY, picks: [priced({ pick: 'B', evPct: 12 })] }),
    ]
    const result = composeUnifiedMatches(predictions, tied, [], {
      ...BASE_FILTERS,
      sort: 'confidence',
    })
    expect(result.map((match) => match.matchId)).toEqual([1, 2])
  })

  it('leaves the input array untouched', () => {
    const input = composeUnifiedMatches(predictions, bests, props, BASE_FILTERS)
    const keys = input.map((match) => match.key)
    sortUnifiedMatches(input, 'start')
    expect(input.map((match) => match.key)).toEqual(keys)
  })
})

describe('normalizeName', () => {
  it('strips accents, punctuation and case', () => {
    expect(normalizeName('Félix Auger-Aliassime')).toBe('felix auger aliassime')
    expect(normalizeName("Miomir  Kecmanović")).toBe('miomir kecmanovic')
    expect(normalizeName(null)).toBe('')
  })
})
