# Feature: Public repo and README

**From build-plan:** feature 37e
**Status:** not started

## Goal

Make the code public, so an employer can read it beside the live demo.

- A new public GitHub repository starts from one commit holding today's tree,
  so none of the private repo's history goes public, rotated-out credentials
  included.
- The public repo becomes the working repo: the scheduled ingest, CI and both
  Render services move to it.
- The private repo is archived as the history backup.
- A README explains what the app is, links the live demo and the How it
  works page, and says how to run it.

## Decisions (proposed 2026-10-16, owner to confirm at review)

- **Repo name: `Sports-Baseline`** (public, chosen by the owner), under `Dayshawn21`. The private
  `SportAppV2` keeps its name and is archived, never deleted.
- **The public repo is the working repo from now on.** Two live repos would
  drift apart, and both would run the crons against one database. Public
  repos also get unmetered Actions minutes.
- **No history.** Pre-37e commits stay in the archived private repo.
  - **Consequence:** `/rollback` of a pre-37e feature reads its commit there,
    since the archives' commit hashes do not exist in the public repo.
- **The interview guide stays private.**
  `docs/SportApp-Employer-Interview-Guide.md` is first-person interview
  coaching, and it would read oddly to the employer it is written for.
  - It is untracked and ignored, and kept locally.
  - `AGENTS.md` still tells agents to maintain it, as a local file.
- **No license file.** The README states the code is shared for review, with
  all rights reserved. Adding MIT later is a one-file change.
- **A one-line disclaimer** in the README: a personal research tool, not
  betting advice.

## In scope

- **Gate:** credential rotation (owner), before anything is published.
- **Tidying the root:** move the stray `design-qa.md` (a 2026-09-19 QA note
  pointing at images that were never committed) into `blueprint/history/`;
  untrack the interview guide.
- **The README,** plus two or three screenshots of the live site.
- **The snapshot:** one orphan commit, pushed to the new repo.
- **The move:** owner actions in GitHub and Render, each listed in a step.
- **Docs:** `AGENTS.md` repo notes, and `project-plan.md` §8 (owner
  approval).

## Out of scope

- Rewriting the private repo's history; it is archived as is.
- A custom domain, a LICENSE file, a contributing guide, issue templates.
- Scrubbing the owner's Windows user name from old archive command logs.
  It matches the public GitHub handle, so nothing private is exposed.
- Branch protection or rulesets beyond turning on push protection.
- README badges beyond the Verify status.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Rotate credentials (owner, gate)** - rotate the Neon
  database password and the Odds-API.io key (open question 47). Put the new
  values in all four places:
  - Render `sportapp-api` env
  - the private repo's GitHub secrets
  - `api/app/.env`
  - `.claude/settings.local.json`

  *Done when:*
  - The live `/health` is 200 and one live data route returns 200 after
    Render restarts.
  - A dispatched NFL Game Weather run passes, which proves the GitHub
    secret.
  - `.venv\Scripts\python.exe -m app.ingest.nfl_slate_snapshot --dry-run`
    connects locally.
  - Nothing is published before this step is ticked.

- [x] **Step 2 - Tidy the tree** - on `feature/public-repo`:
  - `git mv design-qa.md blueprint/history/design-qa-nfl-slate-2026-09-19.md`
  - `git rm --cached docs/SportApp-Employer-Interview-Guide.md`, plus a
    `.gitignore` entry with a one-line reason
  - `AGENTS.md`'s guide section says the file is local and untracked

  *Done when:*
  - The guide still exists on disk and `git status` no longer lists it.
  - A local gitleaks `dir` scan of `git archive HEAD` passes with
    `.gitleaks.toml`, the same scan the CI job runs. Use the pinned 8.28.0
    binary in the scratchpad.
  - `git grep` finds no `postgresql://` URL with real credentials.

- [x] **Step 3 - Screenshots** - capture, with Playwright from the live site
  at 1440 x 900, into `docs/screenshots/` (PNG, each under 400 KB):
  - the tennis slate
  - an NFL game page
  - the NFL model page

  *Done when:* the files exist, and each one shows loaded data, not a
  loading or error state.

- [x] **Step 4 - README.md** at the repo root, written for an employer
  skimming it in two minutes. Sections:
  - **Opening:** one paragraph on what the app is, the live demo URL, and the
    How it works link.
  - **What it shows:** the screenshots.
  - **What I found:** the honest result. The tennis market beat every model,
    so moneyline picks are off. NFL props and game lines are under forward
    validation, and green appears only past 2 SE.
  - **Architecture:** the API, web, Neon, GitHub Actions ingest and Render,
    as a short list.
  - **Stack.**
  - **Running locally:** API and web commands, `api/.env.example`,
    migrations, and the Verify command.
  - **Deployment:** `render.yaml`, stored reports, and why.
  - **Repo map:** `api/app` layers, `web/src`, and `blueprint/` (the AI
    workflow and every feature's spec and evidence).
  - **Disclaimer and rights.**

  *Done when:*
  - The README has no em dashes, only links that resolve (relative links to
    tracked files, live URLs returning 200), no `/api` proxy instructions
    for production, and no claim the code does not back. Every number in it
    is taken from the overview or an archive.
  - Verify passes.

- [x] **Step 4b - Keep tennis best picks off the event loop (added
  2026-10-16, owner)** - a cold `/tennis/predictions/best-picks` held the
  loop for about 4.4 s (Step 3), so visitors opening NFL right after the
  tennis landing page waited 10 to 16 s.
  - **Find it first:** time the route's synchronous sections locally, the
    same way 37d's 9d measured loop stalls.
  - **The change:** the route keeps its database reads async and runs the
    CPU part through `asyncio.to_thread`, as 9d did for `build_slate`.
  - **No logic change:** the best-picks output is unchanged.

  *Done when:*
  - Best-picks JSON for a fixed date is byte-identical before and after.
  - The longest local loop stall during a cold best-picks build is under
    1 s.
  - Verify passes.
  - After the deploy, a concurrent `/nfl/current-week` stays under 1 s
    while a cold best-picks request runs.

- [x] **Step 5 - Create the public repo and push the snapshot (owner yes)**
  1. **Owner:** create an empty public `Dayshawn21/Sports-Baseline`, with no README,
     license or `.gitignore`.
  2. **Me, after a separate yes:**
     - rename remote `origin` to `private`, and add the new repo as `origin`
     - create an orphan branch from the merged tree, with one commit:
       `feat: SportApp, a sports betting research app (public snapshot)`
     - push it as `master`
     - point local `master` at it
     - keep `private/master` as a local ref to the full history

  *Done when:*
  - The public repo has exactly 1 commit.
  - Its tree equals the private `master` tree after Steps 2 to 4.
  - Its Verify run is green: both jobs, the secret scan's range being that
    one commit.

- [ ] **Step 6 - Move the running parts (owner actions)**
  1. **Secrets:** add `DATABASE_URL`, `ODDS_API_KEY`, `THE_ODDS_API_KEY` and
     `LIVETENNIS_API_KEY` to the public repo's secrets, with the rotated
     values.
  2. **Turn on** secret scanning and push protection (free on public repos).
  3. **Render:** repoint `sportapp-api`, `sportapp-web` and the Blueprint
     to `Dayshawn21/Sports-Baseline`, `master`.
  4. **Archive** the private repo (Settings, Archive). This stops its
     scheduled workflows, so the crons never run twice against the
     database.

  *Done when:*
  - Dispatched runs of NFL Game Weather and the tennis ingest pass on the
    public repo.
  - Both Render services deploy the public commit and read Live.
  - The private repo shows "archived".
  - No scheduled run appears on it afterwards.

- [ ] **Step 7 - Public logs check (no code)** - read the public repo's
  first ingest logs and Summary pages for the database host, a key, or an
  `apiKey=` value that GitHub did not mask. `httpx` logs request URLs, and
  several ingests put the key in the query string. GitHub masks exact secret
  values, and this step confirms it.

  *Done when:* no unmasked secret or database host appears. Otherwise,
  delete the run's logs and open a `/fix` before the next scheduled run.

- [ ] **Step 8 - Docs** - these files change:
  - `AGENTS.md`: the repo is public, the private repo is archived for
    history, and where pre-37e commits live.
  - A proposed `project-plan.md` §8 line (the public repo and the archived
    private one), shown for approval.
  - The interview guide, locally: the public repo link replaces "runs from
    the private repository".

  *Done when:* the diffs are reviewed and the §8 edit is approved or
  declined.

## Files / areas

- `README.md`, `docs/screenshots/*.png` (new)
- `.gitignore`, `AGENTS.md`, `design-qa.md` (moved)
- `docs/SportApp-Employer-Interview-Guide.md` (untracked, kept locally)
- `blueprint/project-plan.md` §8 (on approval)
- No app code change is expected. If Steps 2 or 7 find a leak in code, it
  becomes its own reviewed step.

## Data / contracts

- **No schema change.**
- **The public repo `Dayshawn21/Sports-Baseline` (load-bearing):** Render deploys
  from it, the crons and CI run in it, and the README's live links point
  out of it. Its `master` is the default branch.
- **Kept from 37d:** the service names `sportapp-api` and `sportapp-web`, the
  live URLs, and the `Verify` workflow and job names.
- **History lives in the archived private `SportAppV2`.** Pre-37e archive
  commit hashes resolve only there.

## Testing

- **No new logic,** so no new unit test. Verify passes before each
  checkpoint and at `/complete`.
- **Evidence:** the gitleaks scan (Step 2), screenshot files (Step 3),
  link checks (Step 4), green public runs (Steps 5 and 6) and the logs
  review (Step 7), all recorded here.
- **Evidence log:**
  - **Step 1 (2026-10-16):** the owner rotated the Neon password and the
    Odds-API.io key.
    - **Render:** it needs only `DATABASE_URL`, because the API's sole
      `ODDS_API_KEY` reader is the tennis live moneyline lookup, which has
      had nothing to feed since 26d. The `render.yaml` entry is removed in
      Step 2.
    - **Live:** `/health` 200, tennis today 200, NFL current week 200, NBA
      ranking 200.
    - **Local:** the `nfl_slate_snapshot` dry run connected with the new
      `.env` (2026 week 6, 14 games, 6,692 lines). One Odds-API.io
      `/events` request with the new key returned 200.
    - **Owner:** Render deployed after the `DATABASE_URL` change, and a
      dispatched NFL Game Weather run on the private repo was green.
  - **Step 2 (2026-10-16):**
    - **Moves:** `design-qa.md` moved to
      `blueprint/history/design-qa-nfl-slate-2026-09-19.md`. The interview
      guide is untracked and ignored, and still on disk.
    - **Render:** the `ODDS_API_KEY` entry is removed from `render.yaml`,
      with a comment saying why, and the Deploy notes list three secrets.
    - **Scan:** gitleaks 8.28.0 (checksum verified) `dir` over
      `git archive` of the staged tree, with `.gitleaks.toml`, scanned
      12.08 MB: "no leaks found". The guide is absent from that tree.
    - **Grep:** `git grep` found no `postgresql://` URL with credentials
      other than `.env.example`'s `user:pass@` placeholder.
  - **Step 3 (2026-10-16):** Playwright at 1440 x 900 on the live site.
    - **Files:** `tennis-slate.png` (125 KB), `nfl-game.png` (LAC @ KC,
      game 90, 145 KB) and `nfl-model.png` (143 KB). Each was retaken after
      its loading text cleared, and each shows loaded data.
    - **Console:** the only error was the known `favicon.ico` 404.
    - **Found: a cold tennis best-picks request blocks the event loop.**
      With `/tennis/predictions/best-picks` cold (5.5 s), a concurrent
      `/nfl/current-week` waited 4.4 s; warm, it answers in 0.13 to 0.29 s.
      After the tennis page, the NFL game page took about 11 s and the NFL
      model page about 16 s to clear their loading states.
      - **Same pattern as 37d's 9d:** CPU work on the event loop.
      - **Not blocking:** `/tennis/props/prizepicks`, `/tennis/props/bet`,
        `/tennis/predictions/today` and `/tennis/model/prizepicks-lines`
        (6.2 s, but concurrent requests stayed fast).
  - **Step 4 (2026-10-16):** `README.md` written; Verify passes (web 530,
    API 2,596).
    - **Writing:** no em dashes, en dashes or ellipsis characters.
    - **Links:** every relative link is a tracked file (`render.yaml`,
      `verify.yml`, the `alembic.ini` template, `.env.example`) or a staged
      screenshot. The live web URL returns 200, and its `#/` routes are
      served by the same page.
    - **The Verify badge** resolves only once Step 5 creates the public
      repo; it is checked there.
    - **Facts checked against the repo:**
      - 45 migrations
      - `lightgbm` and `scikit-learn` in `requirements.txt`. XGBoost was
        dropped from the README: the overview lists it, but it is not
        installed.
      - Vite 7, so Node 20.19 or newer
      - the 26c and 26d and 27a numbers, taken from the overview
    - **README order changed (owner):** the NFL game page leads; the tennis
      slate moved under "What it shows", with a caption saying a large EV
      there is the model's estimate, not a validated edge. The opening now
      says "an edge is measured rather than assumed".
  - **Step 4b (2026-10-16):**
    - **Live diagnosis:** a cold `best-picks?match_date=2026-10-17` took
      5.9 s. `/health` probes sent every 0.25 s all waited for one 5.2 s
      block; probe 2 took 5.35 s.
    - **Locally the same build stalls at most 0.32 to 0.58 s,** so the
      half-CPU instance amplifies something about 10 times.
      - The likeliest cause is LightGBM's default of one thread per visible
        core, on single-row predicts under a CPU quota.
      - Also on the loop: the history index rebuild over 38,632 matches
        (0.2 s locally), the per-match feature loop and the best-picks
        assembly.
    - **Change:**
      - `predict_lgbm` passes `num_threads=1` under a class-level lock.
      - `HistoryCache` builds its indexes in a worker thread, behind an
        `asyncio.Lock`.
      - `predict_matches` runs its predict-from-cache loop, and
        `_build_best_picks` its assembly, through `asyncio.to_thread`.
      - Database reads stay async.
    - **No output change:** predictions for 2026-10-16 and 10-17 (58,
      sha `7b26443926efb70f`) and best picks (58, sha `ed97532a6351d703`,
      84,041 B) were identical before and after, with live odds off.
    - **Stalls:** the longest local stall went from 0.32 to 0.58 s down to
      0.08 s.
    - **Tests:** 1 new test (a single row predicts on one thread). API
      2,597 pass and web verify passes.
    - **Live (after Render deployed from `Sports-Baseline`):** a cold
      `best-picks?match_date=2026-10-17` took 1.88 s, against 5.9 s
      before. `/health` probes every 0.25 s peaked at 0.57 s, against
      5.35 s before.
  - **Step 5 (2026-10-16):**
    - **Repo:** the owner created an empty public `Dayshawn21/Sports-Baseline`.
      The name was the owner's choice; the README and the app keep
      "SportApp". The owner also asked whether to make the private repo
      public instead. A full-history gitleaks scan (177 commits) found the
      old Neon URL with its host in 3 commits, an ingest log with the old
      Odds-API.io key in 436 lines, and the interview guide in 7 commits,
      so the fresh snapshot was kept.
    - **Snapshot:** checkpoint `62f07a8` on `feature/public-repo`, then
      `git commit-tree` of its tree with no parent gave `2312f3a`. Its tree
      is identical to the checkpoint, and it holds 988 files, with no
      interview guide, `.env` or log.
    - **Scans:** gitleaks `dir` on the archive and gitleaks `git` on
      `-1 2312f3a` both found no leaks.
    - **Remotes:** `origin` was renamed `private`, and the public repo
      added as `origin`. The snapshot was pushed as `master` (the default
      branch, public), and local `master` tracks it.
    - **CI:** public Verify run 38989021876 on `2312f3a` succeeded, with
      both the Secret scan and Verify jobs green.

## Notes for the AI

- **Stop for a separate explicit yes** before creating anything remote,
  pushing, changing remotes, or deleting anything.
  - Repo creation, secrets, Render repointing and archiving are owner
    actions; give click paths, not commands.
- **Never write a secret** into the README, the spec, a commit or a pasted
  log. Step 1's values go only where it lists.
- **The README must stay honest:**
  - Planned, accruing and adopted are kept distinct, as in the overview.
  - No model is claimed to beat the market.
  - The track record pages are linked rather than quoting numbers that
    change weekly; only frozen holdout results are quoted.
- **Writing rules:** no em dashes, and green is described as a signal color
  only.
- **The overview is generated.** Don't hand-edit it; `/complete` updates it.
- **Public repos disable scheduled workflows after 60 days with no
  commits.** Any commit resets the clock, so this matters only in a long
  quiet spell; record it in `AGENTS.md` in Step 8.
- **The local `ingest_daily` task** runs from this working folder, so it is
  unaffected by the remote swap.
