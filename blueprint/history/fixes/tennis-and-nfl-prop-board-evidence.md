# Tennis and NFL prop board evidence fixes

**Type:** Fix

## The problem

The Tennis Props board presents model-only `Win a Set` picks as unpriced rows,
but does not provide a concise confidence signal to help the user prioritize
them. Its selected-line evidence also lacks exact recent-match stat context.

The NFL Prop Board needs reliable kickoff filtering and richer evidence. Past
games can remain visible, anytime-TD rows can be ordered by an incomparable raw
edge, and the board sends users away instead of explaining the selected signal
in place.

## The fix

Add deterministic `Strong` and `Lock` labels for model-only Win a Set rows,
derived from the existing match-model probability. Keep the category clearly
unpriced and outside priced-EV/actionable rankings. Do not add backend routes,
tables, or projection logic for those strength labels. Extend Tennis recent-form
evidence with stored TennisAbstract match statistics.

For NFL, normalize ingested kickoff timestamps to UTC, remove started games from
the Prop Board, rank anytime-TD rows by model probability, and keep the selected
signal on the page with recent, opponent, and opponent-allowed evidence. Do not
change the live projection model.

## Build steps

1. [x] Extend the Tennis board view-model helper to classify eligible Win a Set
   model probabilities into `Strong` and `Lock`, and render the label in both
   the board row and selected evidence panel.
   - Done when qualified Win a Set entries visibly carry one of the labels and
     ordinary model-only entries do not imply a priced EV.
2. [x] Add fixed-input unit tests for the thresholds and run the frontend test
   suite.
   - Done when all tests pass.
3. [x] Apply a 50% model-win-probability floor to actionable Moneyline rows.
   - Done when lower-probability moneyline longshots appear only under `Show all lines` with a clear reason.
4. [x] Exclude non-positive-EV prop rows from the actionable board ranking.
   - Done when an over-only offer with a negative EV appears only under `Show all lines`.
5. [x] Make the daily player-stat refresh honor each player's saved TennisAbstract
   slug, and save the verified Elena-Gabriela Ruse mapping.
   - Done when the batch passes `ta_slug` to its fetcher and Ruse can refresh
     through the existing admin fetch endpoint.
6. [x] Add coverage for the saved-slug batch path and run the API test suite.
   - Done when the regression test and API tests pass.
7. [x] Omit PrizePicks Goblin alternate lines from the Tennis Props board.
   - Done when Goblin offers do not appear in either normal or `Show all` board rows.
8. [x] Add a typed tennis-form response for the two players in one selected match,
   with five correctly oriented, newest-first completed results and their last-52-week serve/return stats.
   - Done when one request returns both players' form without a slate-wide N+1 query,
   and repository coverage verifies ordering, player orientation, and stat mapping.
9. [x] Add a TanStack Query hook and show real last-five completed-match form for
   the selected player and opponent in the Tennis Props evidence panel.
   - Done when the panel shows each player's opponent, date, score, and win/loss
     state, or clearly says history is unavailable.

10. [x] Persist exact TennisAbstract player-match box scores for the prior 12 months.
    - Done when the daily player-stat refresh idempotently stores aces, double
      faults, break chances, break conversions, and defensive break data under a
      stable TennisAbstract row key.
11. [x] Add a rate-limited active-slate history backfill mode.
    - Done when active players can collect the same 12-month history without
      re-fetching or duplicating rows on a retry.
12. [x] Extend selected Tennis Props evidence with exact last-five core prop
    results for both players.
    - Done when aces, double faults, and break conversions/chances appear beside
      the existing score and W/L history, with an explicit unavailable state.
13. [x] Add a chronological offline validation report for candidate raw-stat
    model features without changing live predictions.
    - Done when the report compares the current baseline with candidate features
      using only pre-match data and records calibration and accuracy outcomes.
14. [x] Keep `breakEvenPct` in percent units on every Tennis board row, matching
    the API's `break_even_pct`.
    - Done when the evidence panel shows a PrizePicks demon break-even as 41.3%,
      not 4130.0%, and moneyline market probability still reads correctly.
15. [x] Show the PrizePicks payout tier (Standard, Demon, Goblin) on board rows
    and in the evidence panel.
    - Done when every PrizePicks row carries its tier badge and priced sources
      carry none.
16. [x] Rank Tennis board rows by confidence tier (Lock, Strong, Lean) before EV.
    - Done when a high-EV Lean row sorts below a lower-EV Strong or Lock row,
      and EV still orders rows within a tier.
17. [x] Orient recent-form set scores to the selected player when they were the
    match's p2.
    - Done when a p2 win stored as "3-6 5-7" shows as "6-3 7-5".
18. [x] Normalize NFLverse kickoff times from Eastern wall-clock time to UTC and
    render kickoff labels explicitly in Central Time.
    - Done when a 1 PM Eastern kickoff persists as 17:00 UTC and displays as noon Central during daylight time.
19. [x] Remove already-started NFL games from the Prop Board while retaining
    future games and rows whose kickoff is unavailable.
    - Done when a game disappears at kickoff without removing it from the full NFL slate.
20. [x] Rank NFL anytime-TD rows by model probability rather than raw edge.
    - Done when the highest projected touchdown probability sorts first.
21. [x] Keep the selected NFL Prop Board signal on the page and show its model,
    line, trust, recent form, opponent history, and opponent-allowed history.
    - Done when selecting a row updates the adjacent evidence panel without navigating away.
22. [x] Remove generated Playwright artifact files from version control.
    - Done when no Playwright capture artifact remains in the repository tree.

## Verify

- Open `/tennis/board`, select `Win a Set`, enable `Show all lines`, and check
  that the strongest model-only entries are easy to identify and retain their
  unpriced label.
- Open `/nfl/props`, select an upcoming prop row, and confirm the evidence panel
  updates in place while already-started games remain absent.
- Run `cd web && npm run test` and `cd web && npm run build`.
- Run `cd api && .venv\Scripts\python.exe -m pytest`.
