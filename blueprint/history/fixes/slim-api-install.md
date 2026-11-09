# Fix: Keep scikit-learn out of the hosted API install

**Type:** Fix
**Branch:** `fix/slim-api-install` (worktree `.claude/worktrees/fix-slim-api-install`, cut from `master` at `5133dfd6`)
**Status:** completed 2026-11-08

## The problem

The hosted API (`sportapp-api`, 512 MB) uses about 237 MB before serving a
request. Measured locally on 2026-11-08 (Windows working set, fresh process):

| `import app.main` with | Memory |
|---|---|
| everything installed | 237 MB |
| scikit-learn unimportable | **188 MB** |
| scikit-learn and pandas unimportable | 161 MB |

No request-path code imports scikit-learn. LightGBM imports it (and pandas)
on its own whenever it is installed, for its optional sklearn wrapper. The
only runtime path that could need it is `ModelRegistry` loading a
`lgbm_tennis_*_calibration.joblib`, and `api/models/` has none.

pandas stays: the admin ELO refresh route (`app/routers/admin.py`) imports
`app.ingest.elo`, which needs it. Dropping pandas too is a separate decision.

## The fix

Give Render its own, smaller install list; everything else keeps the full one.

- `api/requirements-api.txt` (new): what the hosted API runs on. Every
  current pin except `scikit-learn` and `pytest`.
- `api/requirements.txt`: becomes `-r requirements-api.txt` plus
  `scikit-learn` (backtests: `nfl_anytime_td`, `nfl_game_context`) and
  `pytest`. Same packages and pins as today, so CI (`verify.yml`) and every
  GitHub Actions workflow install exactly what they install now.
- `render.yaml`: `buildCommand: pip install -r requirements-api.txt`, with a
  one-line comment on why.
- Guard tests in `api/tests/test_api_install.py`:
  - `app.main` imports in a subprocess with `sklearn` made unimportable, so a
    future request-path use of scikit-learn fails CI instead of the deploy
  - `requirements-api.txt` does not list `scikit-learn`, and
    `requirements.txt` includes it via `-r` (the two cannot drift apart)
  - `api/models/` holds no `*_calibration.joblib`, since loading one needs
    scikit-learn at startup; adding one must also move scikit-learn back

**Must not change:** any app code, any package version, what CI or the
workflows install, predictions (LightGBM's `Booster.predict` does not use
scikit-learn).

## Build steps

- [x] **Step 1 - Split the install and add the guard tests.** Done 2026-11-08:
  4 guard tests pass; with sklearn blocked, startup fell 257 -> 208 MB and five
  endpoints (both tennis prediction days, 331 LightGBM probabilities, NBA and
  NHL slates, NFL ranking) matched the full install exactly; `pip --dry-run`
  reads all 23 pins through the nested file; Verify passed (web 1,285 tests and
  build, API 5,974).
  - The two requirements files, the `render.yaml` line, the tests.
  - Prove it locally: with `sklearn` made unimportable, start the API
    (memory probe) and request `/tennis/predictions/today` (runs LightGBM)
    plus the slates; every response matches the full install, and startup
    memory drops by about 49 MB.
  - `AGENTS.md` Deploy section: one line that Render installs
    `requirements-api.txt`, so a new runtime dependency goes there.

  *Done when:* the guard tests pass; the sklearn-blocked probe returns the
  same predictions as the full install with startup about 49 MB lower; Verify
  passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- After deploy (separate yes to push): Render's build log shows
  `requirements-api.txt` and no scikit-learn; `/health` and `/tennis` load;
  the Metrics tab shows a lower idle line than before.

## Out of scope

- Dropping pandas (needs the admin ELO route moved to a workflow).
- Lazy-loading `anthropic` (Ask Lineform is used in production).
- The NFL slate payload (the next fix).

## Notes for the AI

- The first Render deploy on the new build command is the real proof; local
  blocking is a strong stand-in, not the same thing.
- Windows working set and Linux RSS differ in absolute terms; quote the
  saving, not the totals, as the expected production change.
