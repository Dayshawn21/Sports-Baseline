# Add NFL matchup odds and team context

**Type:** Fix

The NFL selected-game workspace now shows the latest game moneyline, home
spread, total, and source book above player props. It also shows each team's
pre-week record, points scored per game, and points allowed per game. The data
uses only completed regular-season games before the selected week.

## Verify

- API tests: 767 passed.
- Web tests: 61 passed.
- Web production build passed.
- Browser verification confirmed DET-BUF and CAR-ATL update their matchup panel
  when selected.
