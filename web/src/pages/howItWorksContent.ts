import type { SPORTS } from '~/utils/sportNav'

export type SportCode = (typeof SPORTS)[number]['code']

export interface SportStatus {
  model: string
  picks: string
  reference: string
  status: string
}

// The one place the page states what each sport serves. An item that changes a
// sport's picks (25c, 27h, an NBA adoption, tennis moneylines back on) updates it.
export const SPORT_STATUS: Record<SportCode, SportStatus> = {
  tennis: {
    model: 'The closing market price, adjusted by an ELO term, with weights fitted on 2022 matches and checked once on 2023-2025.',
    picks: 'Derived, serve-edge and book-priced Total Games and Game Spread picks, with their expected value.',
    reference: 'Moneyline picks are off: the model\'s moneyline disagreements lost money against the closing line.',
    status: 'PrizePicks props carry no confidence tier: each line shows its projection and P(over) against the payout\'s break-even, gray and unranked unless a forward check of lines frozen before each match adopts its slice; only adopted lines are ranked and shown green.',
  },
  nfl: {
    model: 'Player-history prop projections; ELO-based game lines.',
    picks: 'None.',
    reference: 'Prop edges, the game-line model, and the best available price beside a fair price.',
    status: 'The prop model graded below the 57.7% break-even, so its edges stay gray. Forward checks of the prop ranking and of game-line movement are still accruing.',
  },
  nba: {
    model: 'A player\'s average over their last 20 games, with an over probability for assists.',
    picks: 'None.',
    reference: 'Projections, gaps to the line, and the assists over probability.',
    status: 'The forward ranking check is accruing from the 2026-27 season.',
  },
  nhl: {
    model: 'A reference prop projection from each player\'s recent games, with an over probability for Shots on Goal, Time On Ice, Goals Allowed and Faceoffs Won.',
    picks: 'None.',
    reference: 'Projections, gaps to the line and those over probabilities, beside stored full-game book prices, per-book market win probability and line movement. A goalie line shows a projection only for an Expected or Confirmed starter.',
    status: 'Projections are frozen before puck drop and graded by a forward ranking check that is still accruing, so every gap stays gray. Goalie and injury reports are ESPN snapshots that may miss late changes, and an empty injury report does not establish availability.',
  },
}
