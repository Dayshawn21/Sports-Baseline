// Numbers from analysis/week01-save-the-season.ipynb (data through week 6, 2026).
// Rerun the notebook and paste fresh values here before each video.
export const data = {
  week: 6,
  game: {label: 'MONDAY NIGHT FOOTBALL', away: 'COWBOYS', home: 'EAGLES'},
  teams: [
    {
      key: 'DAL',
      name: 'Dallas',
      record: '2-4',
      offenseRank: 8,
      defenseRank: 32,
      actualWins: 2,
      pointsSayWins: 2.8,
      playoffOneIn: 5,
    },
    {
      key: 'PHI',
      name: 'Philly',
      record: '2-4',
      offenseRank: 30,
      defenseRank: 28,
      actualWins: 2,
      pointsSayWins: 2.1,
      playoffOneIn: 8,
    },
  ],
};

export const theme = {
  bg: '#000000',
  accent: '#09BDFE',
  text: '#f5f5f7',
  text2: '#9a9aa3',
  gray: '#6b6b75',
  grayLow: '#2a2a30',
};
