# Current Feature

## Tennis surface override and finished-match prop label

**Type:** Fix

## The problem

1. **Provider surface error.** livetennisapi files this week's Lyon (France)
   event, main draw (`tournament_id` `14767`) and qualifying (`14763`), as
   `Clay` with `indoor` null. The event is indoor hard. The ingest copies the
   provider value (`_map_surface` in `app/ingest/livetennis.py`), so 27 stored
   matches (2026-10-18 to 10-21) carry the wrong surface. Re-running
   `ingest_daily.bat` on 2026-10-21 kept them `Clay`. Surface is a model input:
   it picks the surface ELO and the surface rolling-stat split for every
   upcoming Lyon prediction and prop projection.
2. **Misleading prop row label.** When a prop's stored match is finished
   (`match_finished` or `match_link_invalid`) and no live match relinks, the
   board has no matchup, so `propCard` (`web/src/utils/tennisPropCards.ts:71`)
   falls back to `tour · surface`, and the surface comes from the stale match
   (`COALESCE(relinked.surface, m.surface)` in `app/repositories/props.py`).
   Nakashima and Berrettini show "Clay" as if it were their next match.
   "Match unavailable" (no match stored at all, as for Bencic, Shnaider and
   Rybakina on 2026-10-22) is correct and stays.

## The fix

1. **Override table in `app/core/`** (pure): `tennis_surface_overrides.py`
   maps a provider `tournament_id` to a corrected `(surface, indoor)`, each
   entry with a one-line reason. `apply_surface_override(tournament_id,
   surface, indoor)` returns the corrected pair, or the inputs unchanged.
   `livetennis.py`'s match normalizer calls it. Keyed by `tournament_id`, not
   the name, so a future clay Lyon edition (May) is not affected. Entries:
   `14767` and `14763` -> `Hard`, indoor `True`.
2. **Correct stored rows** by re-running match ingest over the window.
   `upsert_match` uses `COALESCE(EXCLUDED.surface, matches.surface)`, so a
   corrected non-null value overwrites. Writes to the shared Neon database,
   so this runs only with the owner's approval.
3. **Label:** in `propCard`, when there is no matchup and the line carries
   `match_finished` or `match_link_invalid`, the meta reads
   `Match finished` (plus tournament if known) instead of `tour · surface`.

**Must not break or change:**

- Stored `predictions` and `prop_projection_snapshots` for Lyon are frozen
  history. They are not rewritten; only predictions made after the
  correction use Hard.
- No change to rateability, ranking, EV, colors or `PROJECTION_VERSION`
  (the projection logic is unchanged; only one input's data is corrected).
- No schema change. H2H `by_surface` splits come from the provider's own
  history, not this field, and are untouched.

## Build steps

- [x] **1. Override module and ingest hook.** Add
  `app/core/tennis_surface_overrides.py` and call it from the livetennis
  normalizer. Tests: an overridden id returns `Hard`/`True`; an unknown id and
  a `None` id pass through unchanged; the normalizer's record for a raw Lyon
  payload carries `Hard`/`True`.
  **Done when:** the new tests and the existing livetennis parser tests pass.
- [x] **2. Finished-match label.** Update `propCard` meta. Tests in
  `tennisPropCards.test.ts`: no matchup + `match_finished` -> `Match finished`;
  no matchup + `match_link_invalid` -> `Match finished`; no matchup, no flags,
  no surface -> empty meta (renders `Match unavailable`); a matched line is
  unchanged.
  **Done when:** web tests pass and the board shows "Match finished" for
  Nakashima and Berrettini.
- [x] **3. Correct stored Lyon rows** (owner approval required, shared
  database). Run `python -m app.ingest.livetennis --days-back 4 --days-ahead 1`
  from `api/`, with `--no-h2h` to avoid unrelated H2H rate limits.
  **Done when:** a read-only query shows every `tournament_id IN ('14763',
  '14767')` row as `Hard`, indoor `true`, and no other tournament's surface
  changed compared with a snapshot taken before the run.

## Verify

- Steps 1 and 2 approved by owner. Verification:
  637 web tests and the production build passed; 3,455 API tests passed.
  Playwright observed Nakashima and Berrettini as "Match finished", Bencic,
  Shnaider and Rybakina as "Match unavailable", and Bouzkova with her matchup.
  Screenshot: `.playwright-mcp/finished-prop-label.png`.
  Browser reported a missing favicon and Ant Design's React 19 compatibility
  warning. Owner authorized step 3's shared-database ingest with `--no-h2h`.
- Step 3 completed with `.venv\Scripts\python.exe -m app.ingest.livetennis
  --days-back 4 --days-ahead 1 --no-h2h` from `api/` (window 2026-10-16
  through 2026-10-21). All 27 Lyon rows were already Hard/indoor before this
  run, consistent with the owner's earlier ingest having corrected them.
  Rerun: 420 normalized, 418 upserted, 0 H2H writes, 0 new players;
  unresolved stubs J. Barranco Cosano and S. D. Lima were skipped.
  Read-only before/after comparison: 41,132 rows each, all 27 Lyon rows
  Hard/indoor, no other tournament's surface changed, no added/removed rows.
  Evidence saved locally in the system temp directory as
  `lineform-lyon-surfaces-before.json` and
  `lineform-lyon-surfaces-comparison.json`.
- Playwright checked next scheduled Lyon match 89084 (Landaluce vs Wawrinka):
  header shows "Hard, indoor"; match-page API requests returned 200 and no
  console errors appeared. Screenshot: `.playwright-mcp/lyon-hard-match.png`.
- No projection version or frozen prediction/snapshot code changed. No
  prediction or prop snapshot refresh was run. No commits, merge or push.
- Findings ledger: F-09 (P3) and F-12 (P2) remain unverified; no open/fixed
  P0/P1 findings. Employer guide unchanged because this small data/label fix
  does not change its claims.
- Verify command passes (`npm --prefix web run verify && cd api && python -m pytest`).
- `/tennis/board`: Nakashima and Berrettini read "Match finished"; Bencic,
  Shnaider and Rybakina still read "Match unavailable"; Bouzkova unchanged.
- The next upcoming Lyon match's page (`/tennis/match/:id`) shows Hard.

## Completion

- Completed locally on 2026-10-20.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv activated: 637 web tests, typecheck and production build
  passed; 3,455 API tests passed.
- Invariants review: clean. Core remains pure; changes are limited to
  tournament-specific input correction and display metadata. No holdout reads,
  projection formula, version, signal color or request-memory changes.
- F-09 and F-12 remain unverified in the findings ledger.
- Manual try: open `/#/tennis/board`, select Aces and Show all lines to see
  finished labels; `/#/tennis/match/89084` shows Hard, indoor.
- Archive prepared for the work commit; merge and push require separate approval.
