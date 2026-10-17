# Remove committed secrets and root clutter

**Type:** Fix

## The problem

The live Neon database URL, password included, is committed in five tracked
files. That blocks publishing the code as a portfolio repo (portfolio plan,
Phase 1):

| File | Where |
|---|---|
| `.claude/settings.json` | line 9, inside an allowed `Bash(...)` permission |
| `.claude/settings.local.json` | line 9 (a `psql` permission) and line 68 |
| `blueprint/history/one-off-scripts/api/check_schema.py` | `DB = '...'` literal |
| `blueprint/history/one-off-scripts/api/check_tseng.py` | `DB = '...'` literal |
| `blueprint/history/one-off-scripts/api/find_dupes.py` | `DB = '...'` literal |

These scratch files are also tracked: `tmp_ta_zverev_output.json` and
`output/playwright/*.png` (8 files in total). `.venv-1/` is not ignored.

Out of scope:
- **Rotating the password and the Odds-API.io key.** The owner does this in Neon
  and Odds-API.io, then updates `api/app/.env` and the GitHub secrets.
- **Rewriting git history.** The public repo will be a fresh snapshot, so the
  old commits never leave this private repo.

## The fix

- **Archived scripts:** replace each `DB = '...'` literal with
  `DB = os.environ["DATABASE_URL"]`. These scripts live outside the app tree
  and are run by hand, so reading the environment directly is fine here. The
  `Settings` rule covers application code only. Nothing else in the scripts
  changes.
- **`.claude/settings.json`:** delete the one permission entry that embeds the
  URL. It was a one-off query allowance, and no workflow needs it.
- **`.claude/settings.local.json`:** untrack it with `git rm --cached`, keeping
  the local file, and add it to `.gitignore`. It is per-machine by design.
  Remove the URL from the local copy too.
- **Clutter:** `git rm --cached tmp_ta_zverev_output.json` and `output/`. Add
  `output/`, `tmp_*.json` and `.venv-*/` to `.gitignore`.
- **Must not break:** app code, tests and workflows. None of them read these
  files. `api/.env.example` keeps its placeholder URL.

## Build steps

- [x] **1. Scrub and untrack.** Make all the edits above in one diff.
  - **Done when:** `git grep -nE "npg_|apiKey=[A-Za-z0-9]{20}|postgresql://[^ ]+:[^ ]+@" -- ':!api/.env.example'`
    finds nothing.
  - **Done when:** `git ls-files .claude/settings.local.json output tmp_ta_zverev_output.json`
    is empty.
  - **Done when:** the local `.claude/settings.local.json` still exists.

## Verify

- Run both `git grep` checks above.
- Run `cd web && npm run build && npm run test` and `cd api && pytest`. Both should
  pass unchanged.
- Run `git status`. Only the intended files should be modified or deleted from
  the index, and no workspace files should be lost.

## Outcome (2026-10-15)

- **Done-whens:** all met. The secret `git grep` on the index finds nothing,
  the three paths are untracked, and the local `.claude/settings.local.json`
  still exists and is now ignored.
- **One change from the spec:** the URL stays in the local, now untracked,
  `.claude/settings.local.json`, because its `postgres` MCP server connects
  with it. Update it after the Neon password reset.
- **Checks:** `npm run build` succeeded. `npm run test` passed 44 files and 520
  tests. `pytest` had 2540 passed and 1 failed:
  `tests/test_nfl_prop_market.py::test_arms_score_only_the_common_subset`
  compares floats exactly (`0.20000000000000007 == 0.2`), and fails the same
  way on a clean `master` worktree. It predates this fix and needs a
  `pytest.approx` fix before the portfolio CI phase.
- **Still open, owner action:** rotate the Neon password and the Odds-API.io
  key. Both remain in this private repo's history, which stays private. The
  public repo will be a fresh snapshot.
