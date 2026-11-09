import type { Sport } from '~/utils/sportNav'

export interface SlateLegendContent {
  parts: { label: string, text: string }[]
  /** The "What's a pick?" sentences. They condense the old legends and `SPORT_STATUS`; never a stronger claim. */
  pick: string[]
}

const FORWARD_CHECK_GAPS = 'Gaps are reference only and stay gray until a forward check on later games passes for that kind of prop.'

// No clock times here: the period line owns the odds time and its stale marker (57a).
export const SLATE_LEGENDS: Record<Sport, SlateLegendContent> = {
  tennis: tennisLegend('PrizePicks'),
  nfl: {
    parts: [
      { label: 'Market', text: 'DraftKings, else the latest book' },
      { label: 'Model', text: 'Elo spread and total, context only' },
    ],
    pick: [
      'No NFL picks.',
      'A prop gap is the model\'s projection minus the prop line, as a share of a typical line for that stat this week.',
      FORWARD_CHECK_GAPS,
      'The Model column is nfl-elo-v1\'s spread and total, for context only: the closing line beat it on 2022-25 games held out of its fitting.',
      'In Notes, Q and D count questionable and doubtful players on the injury report.',
    ],
  },
  nba: {
    parts: [
      { label: 'Market', text: 'DraftKings, else the latest book, de-vigged' },
      { label: 'Scores', text: 'the morning after' },
    ],
    pick: [
      'No NBA picks.',
      'A prop gap is the reference projection minus the prop line, in units and as a share of that line.',
      FORWARD_CHECK_GAPS,
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
      'Win probability removes each book\'s margin (de-vig), and props show the line only, with no projection.',
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
      'Model lean is the side the model favors in each match, shown gray because it is not a pick.',
      'A Total Games or Game Spread pick shows its expected value only when a book price is stored.',
      'Moneyline picks are off: the model\'s moneyline disagreements lost money against the closing line.',
      'PrizePicks lines stay gray and unranked until a forward check on later matches passes for that kind of line.',
    ],
  }
}
