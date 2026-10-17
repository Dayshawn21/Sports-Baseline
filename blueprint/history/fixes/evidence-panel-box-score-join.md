# Fix: Evidence panel box-score join

**Type:** Fix
**Status:** complete

## The problem

The Tennis page's match evidence panel shows each player's last 5 completed
matches with aces, double faults, break chances created and break points
converted. It gets them from `get_recent_completed_matches` in
`api/app/repositories/matches.py`, which joins `player_match_stats` on the
**exact** `match_date` and result. It is called by `GET
/tennis/matches/{match_id}/recent-form`.

TennisAbstract dates box scores by tournament start (26e), so that join is:

- **Mostly empty.** Over the last 60 days of ATP and WTA matches, it finds stats
  for 404 of 2,826 player-matches (14.3%). 26e's `join_box_score` finds 2,276
  (80.5%), measured 2026-09-25.
- **Sometimes wrong.** A player's wins in one event share the tournament-start
  date, so a first-round date can pick up another round's box score (the query
  takes the newest fetched row).

## The fix

Drop the lateral box-score join from the recent-matches query. Then, for the
(player, match) pairs it returns, load candidates with 26e's
`get_box_score_candidates` and join them with `BoxScoreContext.join()`. Take the
four numbers from the joined candidate. An unjoined match shows blanks, as it
does today.

Must not break:

- the response shape (`RecentMatchResult` and its schema) and each player's
  newest-first order
- the p2 score flip
- the 404 for an unknown match

The panel is pre-match context for past matches only, so there is no leakage
concern.

`BoxScoreCandidate` lacks `break_chances_created`, which the panel shows. Add it
as an optional last field (default None), and select it in the candidate
loader. The existing positional constructors keep working.

## Build steps

- [x] **Step 1 - Carry break chances on a candidate.**
  - Add `break_chances_created: int | None = None` to `BoxScoreCandidate` in
    `app/core/box_score_join.py`.
  - Select `s.break_chances_created` in `get_box_score_candidates`, and map it
    in `group_candidate_rows`.

  *Done when:* `tests/test_box_score_candidates.py` shows the column selected
  and mapped, and the full suite passes.
- [x] **Step 2 - Recent form uses the join.** In `get_recent_completed_matches`:
  - select `m.id` and drop the `LEFT JOIN LATERAL` on `player_match_stats`
  - call `get_box_score_candidates` for the returned pairs
  - fill the four stats from each pair's joined candidate, or None

  *Done when:*
  - `tests/test_match_recent_form.py` is updated for the new query shape and
    shows a joined match with its numbers, an unjoined match with blanks, and
    the p2 flip and newest-first order unchanged.
  - The router test still passes.
  - A live call to `/tennis/matches/{id}/recent-form` for a recent ATP or WTA
    match shows aces on most rows, where it showed mostly blanks before.

## Verify

- Suite: `cd api && .venv\Scripts\python.exe -m pytest`.
- Live, API running:
  `curl http://127.0.0.1:8000/tennis/matches/<recent match id>/recent-form`.
  Compare the count of non-null `aces` across both players' matches before and
  after.
- UI: open the Tennis page, expand a match's evidence panel, and check that
  recent matches now show aces and double faults.

## Notes for the AI

- **Reuse 26e's join, don't reimplement it:** `get_box_score_candidates`,
  `BoxScoreContext.join()` and `join_box_score`.
- **Keep the SQL in repositories.** `matches.py` may call the
  `player_match_stats` repository function; nothing in the router changes.
- **Two queries instead of one.** The candidate load is one extra round trip per
  request, batched for all 10 matches. That is acceptable for a panel opened on
  demand.
- **The existing tests use a positional fake `execute`** that yields fixed row
  tuples in order. The second query needs its own fake result, or a monkeypatch
  of `get_box_score_candidates`. Prefer the monkeypatch, so the test stays about
  this function.
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the why.
