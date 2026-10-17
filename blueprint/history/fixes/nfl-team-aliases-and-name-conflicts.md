# Fix: Provider team-code aliases and single-match name conflicts

**Type:** Fix
**Status:** complete (2026-09-18)

## The problem

Two linking bugs in PrizePicks NFL prop lines share one root cause: provider
team codes are compared raw against NFLverse codes.

1. **Jaguars and some Rams lines never reach the slate.** PrizePicks sends
   `JAC` and sometimes `LAR`, while `nfl_teams` holds NFLverse's `JAX` and `LA`.
   `find_game_id` looks games up by code, so all 723 stored `JAC` lines and all
   273 `LAR` lines have `game_id` NULL. The slate joins on the game, so they are
   invisible. (`LA` lines, 251, link fine.) These are the only provider codes
   not in `nfl_teams`.
2. **A single name match is accepted even when everything else disagrees.**
   `resolve_player` returns `UNIQUE_NAME` as soon as the initial-plus-surname key
   has one candidate, before any check. PrizePicks "Camden Brown" (DAL, WR) has
   no stats, so he is not stored, and "C. Brown" matched only Chase Brown (CIN,
   RB). 19k's `team_not_in_game` flag exposed it on the 2026 week 2 slate, where
   the line can still show an edge.

Measured over all 18,582 stored `UNIQUE_NAME` links:

| Disagreement | Lines | What they are |
|---|---|---|
| Position | 3 | Travis Hunter (WR/CB, real two-way), Hunter Luepke (FB/RB, labeling), Camden Brown (wrong) |
| Team | 944 | `JAC`/`JAX` 722, `LAR`/`LA` 221 (code aliases), `DAL`/`CIN` 1 (Camden Brown) |
| Full name | 18 | Joshua/Josh Palmer 16, Matt/Matthew Hibner 1 (nicknames), Camden/Chase Brown 1 |
| Full name **and** team | 1 | Camden Brown only |

So neither position nor team alone can veto a single match without breaking
correct links, but "full name and aliased team both differ" catches exactly
the bad one.

## The fix

1. One pure `canonical_team_code(code)` in `app/core/nfl_names.py` with an
   explicit alias map, `{"JAC": "JAX", "LAR": "LA"}`. That's only the codes
   observed, with no guessing at others. `find_game_id` and the resolver's team
   comparison both use it.
2. In `resolve_player`, a single candidate is rejected with a new, unmatched
   reason `name_team_conflict` when **both** hold:
   - the provider's full-name key and the candidate's full-name key exist and
     differ, and
   - the canonical provider team and the candidate's team exist and differ.

   Either signal alone still resolves, as today. That keeps nicknames (same
   team) and traded players (same full name) linked.

**Must not break:**
- **The existing rules:** aliases, nickname links, and the "team never vetoes a
  tie" rule for multiple candidates.
- **The resolver's guiding rule** ("a wrong link is worse than no link"): the
  new reason is an unmatched outcome, like `contradicted`.

## Build steps

- [x] **Step 1 - Team-code aliases for game linking and team comparison.** Add
  `canonical_team_code` with the alias map, and use it in `find_game_id` and
  wherever the resolver compares teams (`_narrow` on team). Tests: `JAC` finds a
  `JAX` game, `LAR` finds an `LA` game, unknown and `None` codes pass through
  unchanged, and a `JAC` provider team narrows to a `JAX` candidate. Then run
  `python -m app.ingest.prizepicks_nfl --relink`, which rewrites stored links.
  *Done when:* `JAC` lines with a game go from 0 to about 723 and `LAR` lines
  from 0 to about 273. Any line that still lacks a game is listed with its
  reason (for example, a start date with no scheduled game). No line's
  `player_id` changes. The 2026 week 2 slate line count rises, and the rise
  comes only from Jaguars and Rams lines.

- [x] **Step 2 - Reject a single match when full name and team both
  conflict.** Add `Resolution.NAME_TEAM_CONFLICT = "name_team_conflict"` (not in
  `MATCHED_REASONS`) and the check on the single-candidate path. Tests:
  - Camden Brown (DAL) against a lone Chase Brown (CIN) is rejected.
  - Joshua Palmer against Josh Palmer on the same team resolves.
  - The same full name on a different team resolves.
  - A nickname with `JAC` against `JAX` resolves.
  - A missing provider team or missing full name resolves as before.

  Then relink.
  *Done when:* the relink changes exactly 1 line, Camden Brown, to unlinked
  with `name_team_conflict` in its outcome counts, and every other outcome count
  is unchanged. The 2026 week 2 slate has 0 `team_not_in_game` lines, and
  Camden Brown's line is counted as unmatched.

## Verify

- API tests (`.venv\Scripts\python.exe -m pytest` from `api/`), web tests, and
  the web build.
- Relink outcome counts recorded before Step 1, after Step 1, and after Step 2.
- `/nfl`, 2026 week 2:
  - a Jaguars game (for example, JAX's week 2 game) shows player props;
  - WAS @ DAL no longer shows Camden Brown as Chase Brown;
  - no red `team_not_in_game` tag appears.

## Implementation notes

- Step 1: `canonical_team_code` in `app/core/nfl_names.py`. The provider team is
  canonicalized once in `resolve_player` (candidate teams are already NFLverse
  codes) and in `find_game_id`. A read-only replay before the relink showed 0
  player links changing. Relink: 996 rows changed (723 `JAC` + 273 `LAR`), and
  outcome counts were identical (`unique_name` 18,582, `full_name` 3,950,
  `no_candidate` 49, `contradicted` 1). Lines with a game: `JAC` 0 -> 723,
  `LAR` 0 -> 273, `LA` 251 unchanged. 2026 wk2 slate: 7,983 -> 8,402 lines. All
  419 new lines are `JAC` (300, DEN vs JAX) or `LAR` (119, LA vs NYG); 0
  existing lines changed or were removed. API tests 862 passed. In the running
  app (confirmed by the user's screenshot), JAX @ DEN shows 597 linked props,
  up from 297.
- Step 2: `_name_and_team_conflict` plus `Resolution.NAME_TEAM_CONFLICT`,
  checked only on the single-candidate path. A read-only replay showed exactly
  1 player link changing (line 19161, Chase Brown 3958 -> none). Relink: 1 row
  changed; `unique_name` 18,582 -> 18,581, `name_team_conflict` 0 -> 1, every
  other count unchanged. 2026 wk2 slate: 8,402 -> 8,401 lines, 0 without an
  opponent, 0 `team_not_in_game`. Camden Brown (DAL WR, anytime TD, game 29) is
  among the 28 unmatched week 2 lines. API tests 867, web tests 76, and the web
  build passed.

## Notes

- Relinking writes stored links in the local database; the Tuesday cron runs the
  same command.
- The alias map covers only PrizePicks codes seen today. A future unknown code
  still fails visibly (no game), rather than being guessed.
- The Odds API prop and game ingests match on team names, not these codes, so
  they are out of scope.
