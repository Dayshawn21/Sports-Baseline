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
    picks: 'Derived, serve-edge and prop picks, with their expected value.',
    reference: 'Moneyline picks are off: the model\'s moneyline disagreements lost money against the closing line.',
    status: 'Prop confidence tiers are still being graded on lines frozen before each match.',
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
    model: 'None.',
    picks: 'None.',
    reference: 'Stored full-game book prices, per-book market win probability, line movement and PrizePicks line-only props. ESPN injuries and Expected/Confirmed starting goalies appear when stored pre-game reports are available.',
    status: 'Goalie and injury reports retain their fetch times and may miss late changes. Empty injury reports do not establish player availability. No projections or pick recommendations are served.',
  },
}
