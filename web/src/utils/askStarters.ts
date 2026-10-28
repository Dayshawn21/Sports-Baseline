import type { Sport } from '~/utils/sportNav'

const GENERAL = [
  'Who plays in the NBA tonight?',
  "What are today's top tennis picks?",
  'How has the NFL model done this season?',
]

const BY_SPORT: Partial<Record<Sport, string[]>> = {
  nba: [
    'Who plays in the NBA tonight?',
    "What are tonight's biggest NBA prop gaps?",
    'How has the NBA model done this season?',
  ],
  nfl: [
    "What's on this week's NFL slate?",
    'Which NFL games are in prime time this week?',
    'How has the NFL model done this season?',
  ],
  tennis: [
    "What are today's top tennis picks?",
    'Which tennis matches are on today?',
    'How has the tennis model done against the market?',
  ],
}

/** Three starter questions for the sport in view; NHL has no Ask tools, so it gets the general set. */
export function askStarters(sport: Sport | null): string[] {
  return (sport && BY_SPORT[sport]) || GENERAL
}
