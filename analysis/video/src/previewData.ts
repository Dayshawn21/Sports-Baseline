// Extra data for the Monday Night Football preview (Cowboys at Eagles, Oct 26, 2026).
// Results and injuries checked Sat Oct 24. UPDATE MONDAY MORNING:
//  - division: the Giants and Commanders play Sunday, so their records will change
//  - injuries: confirm final statuses on the official injury report / team sites
//  - scenarios: fill in from the notebook's "win tonight vs lose tonight" run;
//    while they are null, that scene is skipped automatically

export type Result = {won: boolean; score: string};

export const preview = {
  results: {
    // oldest to newest
    DAL: [
      {won: false, score: '20-28'},
      {won: true, score: '37-20'},
      {won: false, score: '31-34'},
      {won: true, score: '34-30'},
      {won: false, score: '16-24'},
      {won: false, score: '13-23'},
    ] as Result[],
    PHI: [
      {won: true, score: '24-22'},
      {won: true, score: '24-20'},
      {won: false, score: '7-27'},
      {won: false, score: '20-24'},
      {won: false, score: '17-19'},
      {won: false, score: '14-25'},
    ] as Result[],
  },
  injuries: [
    {
      team: 'Dallas',
      asOf: 'as of Sat, Oct 24',
      title: ['Help on the way', 'for that defense?'],
      source: 'Source: Dallas Cowboys',
      items: [
        {player: 'DeMarvion Overshown', pos: 'LB', status: 'Returning', highlight: true, note: 'Out since Week 1 (hamstring), limited snaps'},
        {player: 'Cobie Durant', pos: 'CB', status: 'Trending toward return', highlight: true, note: ''},
        {player: 'Dee Winters', pos: 'LB', status: 'Out', highlight: false, note: 'Achilles strain'},
      ],
    },
    {
      team: 'Philly',
      asOf: 'as of Sat, Oct 24',
      title: ['Philly lost its QB', 'for the season'],
      source: 'Sources: AP, Sports Illustrated',
      items: [
        {player: 'Jalen Hurts', pos: 'QB', status: 'Out for the season (IR)', highlight: true, note: 'Blood clots; expected to fully recover'},
        {player: 'Tanner McKee', pos: 'QB', status: 'Started last week', highlight: false, note: '26 of 45, 215 yards in a 25-14 loss'},
        {player: 'Saquon Barkley', pos: 'RB', status: 'Questionable', highlight: false, note: 'As of Oct 21'},
      ],
    },
  ],
  division: {
    name: 'NFC East',
    asOf: 'before Sunday’s games',
    rows: [
      {team: 'Giants', record: '3-2-1', pct: 0.583, playing: false},
      {team: 'Cowboys', record: '2-4', pct: 0.333, playing: true},
      {team: 'Eagles', record: '2-4', pct: 0.333, playing: true},
      {team: 'Commanders', record: '1-4-1', pct: 0.25, playing: false},
    ],
  },
  // Playoff chance in % if each team wins / loses tonight. Fill from the notebook.
  scenarios: null as null | {DAL: {win: number; lose: number}; PHI: {win: number; lose: number}},
  rematch: 'Thanksgiving, Nov 26 in Dallas',
};
