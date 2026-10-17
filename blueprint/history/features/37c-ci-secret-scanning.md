# Feature: CI and secret scanning

**From build-plan:** feature 37c
**Status:** complete

## Goal

Give local work and GitHub one shared `Verify` command (web typecheck, web
tests, API tests, web build) and a GitHub Actions workflow that runs it on
every pull request and every push to `master`, beside a secret-scan job that
fails when a pushed commit or the tracked tree carries a credential. This is
the safety net the public demo (37d deploy, 37e public repo) relies on: a
broken build or a leaked key must show red before it reaches a public page.

## In scope

- **`verify` script in `web/package.json`**: `tsc -b && vitest run && vite build`
  (typecheck, tests, build, the `/ci` order; `npm run build` already runs
  `tsc -b`, so `verify` calls the pieces directly rather than typechecking twice).
- **One documented `Verify` command** in `AGENTS.md` Commands, covering both
  apps: `npm --prefix web run verify && cd api && python -m pytest`.
- **`.github/workflows/verify.yml`** (the path is free), two jobs:
  - `verify`: Node 24 and Python 3.11, `npm ci` in `web/`, `pip install -r
    api/requirements.txt`, then the exact `Verify` command. `DATABASE_URL` is a
    password-free dummy (`postgresql://localhost/ci`), because `Settings`
    requires it at import and no test connects (repository tests use recording
    fake sessions).
  - `secret-scan`: a pinned gitleaks release binary, two scans:
    - **tree**: every tracked file at the checked-out commit (catches a
      credential in the current code whatever the commit range);
    - **range**: the commits the event brings in (`before..after` on push,
      `base..head` on a pull request; falls back to the head commit alone when
      `before` is all zeros), so a key added and then deleted in the same
      push still fails.
- **`.gitleaks.toml`** at the repo root: extends gitleaks' default rules.
  A path is allowlisted only when a step's evidence shows a specific false
  positive, listed by path with a one-line reason (step 3 found one).
- Triggers: `pull_request`, `push` to `master`, `workflow_dispatch`.
  `permissions: contents: read`. `concurrency` cancels a superseded run on the
  same ref.
- Docs: `AGENTS.md` (Verify command, remove "no combined Verify yet"),
  `coding-standards.md` Verification section, and the employer interview guide
  (CI and secret scanning are an operational capability).

## Out of scope

- **Pushing the workflow.** It does nothing on GitHub until the owner approves
  a push (`/complete` asks separately).
- **Requiring the check** with a branch ruleset, and **GitHub push protection**
  (which blocks a push outright, rather than failing a check after it). Both
  are remote settings for the owner, best enabled once 37e makes the repo
  public (push protection is free on public repos).
- **Scanning this private repo's full history.** It still holds the rotated-out
  Neon URL and Odds-API.io key (open question 47); 37e publishes a fresh
  snapshot instead, so the range scan only ever reads new commits.
- Lint, coverage, dependency audits, browser tests, version matrices, local
  git hooks (`/ci` rules).
- Changes to the 11 existing scheduled ingest workflows.
- Deployment (37d) and the README (37e).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Verify command** - add the `verify` script to `web/package.json`
  and the `Verify` line to `AGENTS.md` Commands (replacing "There is no combined
  `Verify` command yet"), with the local note that `python` must be the API venv
  (activate `api/.venv`, or run the two halves with
  `.venv\Scripts\python.exe -m pytest`). *Done when:* `npm --prefix web run verify`
  passes (tsc clean, every Vitest file passes, `web/build` written); `pytest`
  passes from `api/`; and pytest also passes in a CI-like environment: with
  `api/app/.env` temporarily renamed and `DATABASE_URL=postgresql://localhost/ci`
  set, the full suite passes with the same count (proves CI needs no secret).
  The `.env` is restored afterwards and `git status` shows only the two
  intended files changed.
- [x] **Step 2 - Verify workflow** - create `.github/workflows/verify.yml` with
  the triggers, permissions, concurrency and the `verify` job only, matching the
  existing workflows' style (`actions/checkout@v4`, `actions/setup-python@v5`
  with pip cache on `api/requirements.txt`, `actions/setup-node@v4` with npm
  cache on `web/package-lock.json`). *Done when:* the file parses as YAML
  (`python -c "import yaml, sys; yaml.safe_load(open(...))"` or equivalent);
  its final step's command is character-for-character the `AGENTS.md` Verify
  command; no existing workflow file is modified (`git status`).
- [x] **Step 3 - Secret scan** - add `.gitleaks.toml` and the `secret-scan` job
  (pinned gitleaks version, checksum-verified download, `fetch-depth: 0` so the
  range exists). *Done when*, using the same pinned gitleaks binary locally
  (downloaded to the scratchpad, never committed):
  - the tree scan of the current branch reports no leaks (exit 0);
  - a planted fake credential in an untracked scratch copy of the tree (for
    example an AWS-format test key) makes the tree scan exit non-zero and
    name the file;
  - the range scan over this branch's commits (`master..HEAD`) exits 0;
  - `api/.env.example` is the only allowlisted path, unless a finding in this
    step justified another, recorded in the step notes.
  - *Step notes:* the default rules never flag `api/.env.example`, so it is not
    allowlisted. They flag one file, `blueprint/history/one-off-scripts/root/tmp_ta_zverev.html`
    (`generic-api-key`): Cloudflare's public analytics beacon token in a saved
    TennisAbstract page. That path is the one exception.
- [x] **Step 4 - Docs** - update `coding-standards.md` Verification (Verify is
  the gate; the three manual commands become the diagnostic fallback),
  `AGENTS.md` Automatic verification (the workflow exists, what it runs, push
  protection and the ruleset are owner settings), and
  `docs/SportApp-Employer-Interview-Guide.md` (CI and secret scanning as
  implemented, not yet seen running on GitHub until pushed). *Done when:* no
  file still claims there is no Verify command (`git grep -n "no combined"`
  finds nothing outside `blueprint/history/` and this spec); the guide distinguishes
  implemented from running on GitHub; the final `Verify` run passes.

## Files / areas

- `web/package.json` - `verify` script
- `AGENTS.md` - Commands and Automatic verification
- `.github/workflows/verify.yml` - new
- `.gitleaks.toml` - new
- `blueprint/context/coding-standards.md` - Verification section
- `docs/SportApp-Employer-Interview-Guide.md` - CI and security passages

## Data / contracts

- **Load-bearing: the `Verify` command** in `AGENTS.md` is the one gate
  `/implement`, `/complete`, `/autopilot` and the workflow all run. Changing
  its checks means changing `AGENTS.md` and `verify.yml` together.
- **Load-bearing: the workflow name and job ids** (`Verify` workflow, `verify`
  and `secret-scan` jobs) are what a later ruleset requires and what 37d's
  Render setup may wait on; renaming them breaks a required check.
- **`.gitleaks.toml`** is the one place scan exceptions live, each by path with
  a reason.
- No schema, API or UI change.

## Testing

- Test gate is on, but this feature adds no application logic: a package
  script, a workflow and a scanner config. Evidence is the local `Verify` run,
  the CI-like pytest run without `.env`, the YAML parse, and the gitleaks clean
  and planted-key runs.
- **Not provable locally:** the workflow's first green run on GitHub. That
  arrives only after the owner approves a push; `/complete` should record it as
  pending, not as passed.

## Notes for the AI

- Follow the `/ci` skill's rules: preserve existing workflows, invent no checks,
  no hooks, never push or change remote settings.
- Never write a credential-looking string into a tracked file, the dummy
  `DATABASE_URL` included (no user:password form), or the scan will flag our
  own workflow. The planted test key lives only in a scratchpad copy.
- Pin the gitleaks release by exact version and verify its checksum; do not use
  `gitleaks/gitleaks-action` (its license-key rules for organizations and its
  scan-range behaviour are less explicit than the CLI's flags).
- Node 24 matches the local `node -v` (v24.22.0); Python 3.11 matches the other
  workflows. There is no `.nvmrc`; do not add one.
- `npm ci` needs `web/package-lock.json` in sync with `package.json`; adding a
  script does not change the lockfile.
- No em dashes in docs, comments or the workflow.

## Outcome (2026-10-15)

- **Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed three times (44 files, 527 web tests, build written; 2567 API tests).
- **CI-like run:** with `api/app/.env` moved aside, API keys unset and
  `DATABASE_URL=postgresql://localhost/ci`, pytest passed at the same 2567, so
  the workflow needs no repository secret.
- **Workflow:** `verify.yml` parses with jobs `verify` and `secret-scan`; the
  `verify` job's last step is character-for-character the `AGENTS.md` Verify
  command; `npm ci --dry-run` passes on the current lockfile; no existing
  workflow was modified.
- **Secret scan** (gitleaks 8.28.0, Windows binary checksum-verified, run in a
  scratch clone so the planted key never touched this repo):

  | Scenario | Exit |
  |---|---|
  | Tree scan of the branch | 0 |
  | Range scan `master..HEAD` | 0 |
  | Tree scan with a planted `ghp_` token | 1 (`github-pat`, file named) |
  | Tree scan after deleting it | 0 |
  | Range scan over add-then-delete commits | 1 (file and commit named) |
  | `-1 HEAD` fallback | 0 |

- **Departure from the spec:** `api/.env.example` is not allowlisted (the
  default rules never flag it). The one exception is
  `blueprint/history/one-off-scripts/root/tmp_ta_zverev.html`, a Cloudflare
  public analytics beacon token in a saved TennisAbstract page.
- **Not yet proven:** the first run on GitHub. It needs the owner to push;
  requiring the check (ruleset) and GitHub push protection are owner settings,
  best enabled after 37e makes the repo public.
- **Interview guide:** the tech table, the testing answer and a new
  secret-scanning answer; CI is described as configured and tested locally,
  not yet running on GitHub.
