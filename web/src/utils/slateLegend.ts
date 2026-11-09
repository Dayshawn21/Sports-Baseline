import type { Sport } from '~/utils/sportNav'

export interface SlateLegendContent {
  parts: { label: string, text: string }[]
  /** The "What's a pick?" sentences. They condense the old legends and `SPORT_STATUS`; never a stronger claim. */
  pick: string[]
}

// No clock times here: the period line owns the odds time and its stale marker (57a).
export const SLATE_LEGENDS: Record<Sport, SlateLegendContent> = {
  tennis: tennisLegend('PrizePicks'),
  nfl: {
    parts: [
      { label: 'Market', text: 'DraftKings, else the latest book' },
      { label: 'Model', text: 'nfl-elo-v1, context only' },
    ],
    pick: [
      'No NFL picks.',
      'Gaps are reference, gray until the ranking check (27j) adopts a slice.',
      'The model is not a pick: the closing line beat nfl-elo-v1 on the 2022-25 holdout.',
    ],
  },
  nba: {
    parts: [
      { label: 'Market', text: 'DraftKings, else the latest book, de-vigged' },
      { label: 'Scores', text: 'the morning after' },
    ],
    pick: [
      'No NBA picks.',
      'Gaps are the reference projection minus the line, gray until the ranking check adopts one.',
    ],
  },
  nhl: {
    parts: [
      { label: 'Prices', text: 'full-game, incl. OT and shootouts' },
      { label: 'Goalies, injuries', text: 'ESPN' },
      { label: 'Scores', text: 'after games' },
    ],
    pick: [
      'No NHL picks or projections.',
      'Prices are stored book prices: DraftKings, else the latest of FanDuel and bet365.',
      'Win probability is de-vigged per book, and props are line-only.',
      'Goalies and injuries are ESPN reports, which may miss late changes.',
    ],
  },
}

/** Tennis names the active prop source, which an admin can switch. */
export function tennisLegend(sourceLabel: string): SlateLegendContent {
  return {
    parts: [
      { label: 'Props', text: sourceLabel },
      { label: 'Odds', text: 'stored book prices' },
    ],
    pick: [
      'Total Games and Game Spread picks carry their expected value.',
      'Moneyline picks are off: the model\'s moneyline disagreements lost money against the closing line.',
      'PrizePicks lines stay gray and unranked unless their forward check adopts the slice.',
    ],
  }
}
