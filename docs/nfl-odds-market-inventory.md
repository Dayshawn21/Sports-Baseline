# Odds market inventory

- Captured at: 2026-09-17T12:43:37.688388+00:00
- Request scope: sport=american-football; one /events request; one /odds/multi request for 10 event(s), up to 10; bookmakers=DraftKings,Bet365

| Bookmaker | Markets |
|---|---|
| Bet365 | Correct Score, Game Lines 3-Way, ML, Player Props, Player Tackles, Spread, Totals, Winning Margin |
| DraftKings | 1st Half Team Total Points Away, 1st Half Team Total Points Home, ML, ML 2H, ML HT, Player Props, Spread, Spread 2H, Spread HT, Team Total (Points - 1st Quarter) Away, Team Total (Points - 1st Quarter) Home, Team Total (Touchdowns) Away, Team Total (Touchdowns) Home, Team Total Away, Team Total Home, Totals, Totals 2H, Totals HT |

## Representative payload shape

- Event fields: away, awayId, bookmakerIds, bookmakers, date, home, homeId, id, league, sport, status, urls
- Bookmaker fields: name/key plus markets (Bet365)
- ML: market fields `name, odds, updatedAt`; odds-entry fields `away, home`
- Spread: market fields `name, odds, updatedAt`; odds-entry fields `away, hdp, home, label`
- Totals: market fields `name, odds, updatedAt`; odds-entry fields `hdp, over, under`
