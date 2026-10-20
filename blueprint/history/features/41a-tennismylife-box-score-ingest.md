# Feature: TennisMyLife box-score ingest

**From build-plan:** feature 41a
**Status:** completed locally and owner approved 2026-10-20; post-push dispatch pending
**Branch:** `feature/tennismylife-box-score-ingest`

## Goal

Store TennisMyLife per-match serve stats as a second `player_match_stats`
source, so the match page's recent form and the player page show box scores
TennisAbstract is missing (558 stored rows with no stats and 443 unstored
player-matches in the 2026-10-20 probe), refreshed daily on GitHub Actions.
Every graded sample (26b line settlement, 26f/32b tier grading, their CLIs)
and every model input stays exactly as it is today.

## In scope

- A pure TennisMyLife parser: one CSV row in, two player-oriented box scores
  out, with TennisAbstract's field semantics.
- A source filter on `get_box_score_candidates`, defaulting to TennisAbstract
  only, so every existing reader is unchanged unless it opts in.
- A pure source-precedence rule in `join_box_score`: a TennisMyLife row is
  used only when no agreeing TennisAbstract row has stats.
- Display readers opt in to both sources: match recent form
  (`app/repositories/matches.py`), and the player page's match log and settled
  props (`app/services/tennis/player_detail.py`).
- `upsert_player_match_stats` takes the source as a keyword (TennisAbstract's
  call unchanged).
- A batched player-name index for resolution (no per-row query).
- `python -m app.ingest.tennismylife [--days-back 21] [--since YYYY-MM-DD]
  [--dry-run]`.
- A daily `tennismylife` job in `.github/workflows/tennis-ingest.yml`, with a
  manual dispatch option.
- The new ingest command in `AGENTS.md`.

## Out of scope

- **Grading readers stay TennisAbstract-only:** `track_record.py` (26b line
  settlement, 32b tier grading), `app/backtest/tennis_prizepicks_lines.py`,
  `app/backtest/tennis_prop_snapshots.py`, and the 26e coverage diagnostic in
  `app/repositories/props.py`. Feeding TennisMyLife into them changes which
  picks settle, and so the pre-registered tier verdict sample. That is a
  separate, owner-reviewed decision, not part of 41a.
- `player_rolling_stats`, prop projections, `PROJECTION_VERSION`, the
  ensemble, LightGBM features.
- Creating players. Unknown names are skipped and counted, never inserted.
- WTA 125 and ITF (TennisMyLife has neither); ELO (41b, 41c).
- Any schema change. `source` and the
  `(player_id, source, source_match_key)` unique key already exist.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure parser** - `app/core/tennismylife.py`: a
  `TmlBoxScore` dataclass and `parse_rows(rows, tour)`, which turns each CSV
  row into a winner box score and a loser box score: player name, tour,
  `match_date` (from `tourney_date`), surface (`Hard`/`Clay`/`Grass`, else
  None), result `W`/`L`, aces, double faults, service games, break points
  faced and saved, break chances created (the opponent's `bpFaced`), break
  points converted (`max(opp bpFaced - opp bpSaved, 0)`), opponent name,
  round, tournament, and the winner-first score. Also `source_match_key`
  (`sha256("tml-v1|<tourney_id>|<round>|<opponent name, trimmed and lowercased>")`).
  A row whose side has no aces, double faults or service games is skipped,
  and so are walkovers. Bad numbers become None, never 0.
  *Done when:* `api/tests/test_tennismylife.py` passes on rows copied from the
  real files (a straight-sets match, a tie-break with `7-6(3)`, a retirement,
  a walkover, a stats-less row, Carpet), and Verify passes.
- [x] **Step 2 - Source filter, TennisAbstract by default** -
  `get_box_score_candidates(db, pairs, *, sources=("tennisabstract",))` filters
  `s.source = ANY(:sources)` **inside the LEFT JOIN's ON clause** (so pairs
  with no box score keep their row) and selects `s.source`.
  `BoxScoreCandidate` gains `source: str = "tennisabstract"`. The 26e
  diagnostic in `props.py` gets `AND s.source = 'tennisabstract'` in both
  subqueries.
  *Done when:* Verify passes. On the current database (no TennisMyLife rows
  yet), `python -m app.backtest.tennis_prizepicks_lines` and
  `python -m app.backtest.tennis_prop_snapshots` print the same output as
  `master`, saved before and diffed.
- [x] **Step 3 - Source precedence, display opt-in** - in `join_box_score`,
  after the score check: if any agreeing TennisAbstract candidate has stats
  (aces or double faults not None), drop the TennisMyLife candidates.
  Otherwise, if any agreeing TennisMyLife candidate has stats, drop the
  TennisAbstract ones. The existing exactly-one, placeholder and
  identical-facts logic then runs unchanged on what is left. `matches.py`
  recent form and both `player_detail.py` calls pass
  `sources=("tennisabstract", "tennismylife")`. The module docstring names
  both sources.
  *Done when:* new tests in `api/tests/test_box_score_join.py` cover:
  - TennisAbstract with stats beats TennisMyLife
  - a TennisAbstract score-only row plus a TennisMyLife row with stats picks
    TennisMyLife
  - TennisMyLife alone joins
  - two disagreeing TennisMyLife rows read `ambiguous`
  - an opponent or score mismatch is still rejected

  Every existing join test passes unchanged, and Verify passes.
- [x] **Step 4 - Source-aware upsert and name index** -
  `upsert_player_match_stats(db, stats, *, source="tennisabstract")` binds
  `:source` instead of the literal. The existing call stays the same.
  `get_player_name_index(db)` in `app/repositories/players.py` loads
  `players` (`name_norm`, `tour`, `id`) and `player_aliases` once. A pure
  `resolve_name(index, name_norm, tour)` in `app/core/tennismylife.py` tries
  the same tour's `name_norm` first, then the alias, mirroring
  `resolve_player`.
  *Done when:* a test covers `resolve_name`: same-name players on different
  tours, an alias hit, a miss, and a name with a non-breaking space or
  accent, normalized first through `normalize_name`. Verify passes.
- [x] **Step 5 - Ingest CLI** - `app/ingest/tennismylife.py`. It downloads
  the current-year ATP, Challenger, ATP qualifying and WTA files plus the
  three ongoing files from `https://stats.tennismylife.org/data/`, using
  httpx with tenacity retries. `--since` also reads earlier years' files.
  It keeps rows with `tourney_date` on or after the cutoff (default today
  minus 21 days), parses them, resolves players, and upserts under
  `tennismylife`. Qualifying lives at `atp_quali/<year>_atp_quali.csv`, and
  Challenger and qualifying rows resolve with tour `ATP`. A match can appear
  in both an ongoing and a yearly file, so the run de-duplicates by
  (`player_id`, `source_match_key`) before writing, keeping the yearly
  file's row. It logs and skips bad rows and unknown players, and fails
  the run only when a file can't be downloaded. It prints counts per file
  family: rows read, kept, skipped for no stats, unknown player, and stored.
  `--dry-run` writes nothing.
  *Done when:*
  1. A `--dry-run` prints counts in line with the probe (thousands of known
     player-matches across ATP, Challenger and WTA).
  2. **With a separate owner yes** (it writes to the shared Neon database),
     a real `--since 2026-01-01` run stores the rows, and a re-run stores no
     duplicates (row count unchanged).
  3. A player-match from the probe's gap set (stats missing from
     TennisAbstract) shows aces and double faults on its match page's recent
     form and on the player page.
  4. The two grading CLIs from step 2 still match their saved `master`
     output.
- [x] **Step 6 - Daily workflow and docs** - a `tennismylife` job in
  `tennis-ingest.yml`: cron `0 11 * * *` (after the 10:00 TennisAbstract
  `player-stats` job), the same setup steps as `player-stats`, and a
  `tennismylife` value in the dispatch `job` input. It runs
  `python -m app.ingest.tennismylife`. Add the command to `AGENTS.md` under
  Ingest. Correct the player match-log note in
  `web/src/components/tennis/player/PlayerMatchLog.tsx` to describe
  TennisAbstract precedence and TennisMyLife filling gaps; its old team-event
  explanation is now inaccurate.
  *Done when:* the workflow YAML parses and the job's `if:` matches both the
  schedule and the dispatch value. After the push (separate approval), a
  manual dispatch run on GitHub succeeds and logs stored counts, which also
  closes the probe's untested question of whether the download works from a
  runner.

## Post-push acceptance

- [ ] After a separately approved push, manually dispatch the `tennismylife`
  job on GitHub and confirm success and stored counts. The owner approved all
  local Step 6 changes on 2026-10-20 with this external check still pending.

## Implementation evidence

- **Step 1 (2026-10-20):** parser, tests and six unaltered CSV fixture rows
  implemented on `feature/tennismylife-box-score-ingest`; owner approved and
  continued without a checkpoint. Focused parser tests: 45 passed.
- **Step 1 Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed with the API venv on PATH: 632 web tests, production build and
  3,069 API tests. Non-failing warnings: Vite bundle size and a dependency's
  deprecated AnyIO alias. The sandbox blocked Vite's parent-directory access;
  the same command passed outside the sandbox.
- **Step 2 (2026-10-20):** source metadata, TennisAbstract-default candidate
  filtering inside the LEFT JOIN, and both 26e diagnostic filters implemented;
  owner approved and continued without a checkpoint. Focused tests: 40 passed.
  Both read-only grading CLIs matched their pre-change `master` output byte for
  byte. Baselines and post-change reports are in ignored `output/41a-step2/`:
  `master_tennis_prizepicks_lines.txt` equals `step2_tennis_prizepicks_lines.txt`
  (6,898 bytes), and `master_tennis_prop_snapshots.txt` equals
  `step2_tennis_prop_snapshots.txt` (4,296 bytes). Before editing, `git diff
  master` confirmed the relevant grading and repository code matched `master`.
- **Step 2 live repository check:** 40 settled pairs retained their contexts
  with `sources=()` and returned zero candidates; default candidates were all
  TennisAbstract; the explicit two-source query also succeeded. Read-only.
- **Step 2 Verify:** the same exact command passed with the API venv on PATH:
  632 web tests, production build and 3,071 API tests. Same non-failing warnings
  as Step 1. No checkpoint commit or database write.
- **Step 3 (2026-10-20):** source precedence added after opponent and score
  checks; the three display calls now explicitly request both sources.
  Owner approved and continued without a checkpoint. Focused tests: 63 passed,
  including all 19 existing join tests unchanged and 18 new precedence cases.
  Display test doubles now require and assert both source names.
- **Step 3 grading comparison:** rerunning the live CLIs differed from the
  earlier Step 2 reports (six more props settled). A comparison loading the
  actual `master` modules and working-tree modules into the same repeatable-read,
  read-only database transaction proved identical coverage, joins and reports:
  46,263 closing lines across 3,674 pairs; 8,517 projection snapshots across
  1,027 pairs. This isolates the difference to changed database inputs, not
  this branch. The comparison script and paired reports are kept locally in
  ignored `output/41a-step3/`; Step 2's original baselines are preserved.
- **Step 3 Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed with the API venv on PATH: 632 web tests, production build and 3,089
  API tests. Same non-failing warnings as Step 1. No checkpoint or database
  write. Checking a real TennisMyLife gap on the pages remains Step 5.
- **Step 4 (2026-10-20):** source-aware upsert (TennisAbstract default), a
  two-query player-name index and pure `resolve_name` implemented. Canonical
  names are scoped by tour; alias fallback is global, matching `resolve_player`.
  Owner approved and continued without a checkpoint. Focused tests: 69 passed,
  covering parser/name resolution and upsert source parameters. New resolution
  cases cover same-name players on different tours, canonical precedence,
  aliases, misses, lowercase tour names, accents and non-breaking spaces.
- **Step 4 live read-only check:** 3,054 canonical names and 124 aliases loaded
  in exactly two SQL reads (counted with SQLAlchemy's execution event); 13
  canonical, alias and missing-name lookups matched `resolve_player`. No writes.
- **Step 4 Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed with the API venv on PATH: 632 web tests, production build and 3,100
  API tests. Same non-failing warnings as Step 1. No checkpoint or database
  write; the source parameter was verified through a recording test session.
- **Step 5, local implementation (2026-10-20):** CLI added with seven current
  files, earlier-year expansion for `--since`, retrying downloads, one name-index
  load, cutoff filtering, yearly-first de-duplication and 500-row upsert batches.
  Writes begin only after all downloads succeed and commit once. Nine ingest
  tests cover file planning, cutoff, de-duplication, malformed rows, unknown
  players, dry-run no-write behavior, batching and a failed last download.
- **Step 5 dry runs:** both live commands succeeded without writes. Default
  `--dry-run` (since 2026-09-29): 1,504 unique known player-matches. `--since
  2026-01-01 --dry-run`: 22,787 (ATP 4,981; Challenger 10,756; ATP qualifying
  2,287; WTA 4,763), zero stored. One ATP row with an empty round was logged and
  skipped; four duplicate qualifying player-matches were dropped. Logs and count
  tables are in ignored `output/41a-step5/`.
- **Step 5 read-only source check:** among completed ATP/WTA matches since
  2026-09-01, 514 WTA player-matches with aces and DFs in both sources had zero
  disagreements in aces, DFs or shared break-point counts. This check did not
  compare service games. Found 148 joined TennisAbstract rows with neither
  aces nor DFs that TennisMyLife can fill; Challenger was outside this diagnostic.
  Gap candidates are saved in `output/41a-step5/compare_sources.json`. Example:
  player 2025 (Elina Svitolina), match 82481 versus Linda Noskova, expected six
  aces and three DFs; choose a subsequent match whose recent form includes it.
- **Step 5 pre-write grading check:** master and working-tree coverage, joins
  and grading reports remain identical on one read-only repeatable-read snapshot
  (46,263 lines / 3,674 pairs; 8,517 projection snapshots / 1,027 pairs).
- **Step 5 Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed with the API venv on PATH after the final test additions: 632 web tests,
  production build and 3,109 API tests. Same non-failing warnings as Step 1.
  No checkpoint or database write at that point. Owner subsequently approved
  the real backfill and repeat in chat; the evidence below closes those checks.
- **Step 5 approved Neon backfill (2026-10-20):** ran
  `python -m app.ingest.tennismylife --since 2026-01-01` twice. First run stored
  22,789 rows (ATP 4,983; Challenger 10,756; ATP qualifying 2,287; WTA 4,763).
  TennisMyLife row count was zero before, 22,789 after the first run and still
  22,789 after the repeat. One upstream ATP match arrived after the dry run,
  explaining the two extra player rows. Both runs skipped the one blank-round
  row and four duplicate qualifying keys. `stored` reports rows upserted, so
  it reads 22,789 again on the repeat; database row count proves idempotency.
- **Step 5 post-write grading:** all 70,587 TennisAbstract rows retained the
  same content fingerprint (excluding fetch timestamps). Both grading CLIs
  produced byte-for-byte identical reports immediately before and after the
  two ingests. Earlier Step 2 master reports predate a TennisAbstract refresh;
  the fixed-input master comparison above and this immediate pre/post check
  isolate the feature's effect. Evidence: ignored `output/41a-step5/`, including
  `backfill_evidence.json`, `pre_write_*.txt`, `post_write_*.txt` and run logs.
- **Step 5 running-app check:** fresh local preview on 3002, current API on
  8002 with WindowsSelectorEventLoopPolicy. Player 2025's log shows match 82481
  versus Linda Noskova with six aces and three DFs. Match 84221's recent form
  shows the same row and counts. TennisAbstract-only candidate still has both
  counts missing; the display's two-source join chooses TennisMyLife.
  Screenshots: `output/41a-step5/player-gap-full.png` and `match-gap.png`.
  All observed player and match API requests returned 200; zero console errors
  in the fresh preview. An initial non-reloading QA server used Windows'
  incompatible Proactor loop; restarting that QA process with the Selector
  policy resolved it without a source edit. The pre-existing server was left
  untouched. Owner reviewed these results and continued without a checkpoint.
- **Step 6 clarification for review:** browser inspection found the player
  match-log footer still says TennisAbstract is the only source and team events
  have no stats. Correcting this source-attribution text is included in Step 6's
  docs scope above. No workflow or product source changes were made during this
  acceptance pass. Step 6 has not started.
- **Step 6 local implementation (2026-10-20):** added the `0 11 * * *`
  schedule and `tennismylife` dispatch option/job to `tennis-ingest.yml`, using
  the same Python/install setup as `player-stats`. Added the CLI and its flags
  to `AGENTS.md`. Corrected the player match-log footer to name TennisMyLife
  gap filling and remove the now-inaccurate team-event explanation. Owner
  approved the local step without a checkpoint; post-push runner acceptance
  remains explicitly pending above.
- **Step 6 workflow check:** PyYAML parsed the file; 14 schedule, dispatch and
  negative event cases passed. The new job selects only `0 11 * * *` or manual
  `job=tennismylife`; existing jobs and global environment are unchanged, setup
  matches `player-stats`, and the job runs `python -m app.ingest.tennismylife`.
  Evidence: ignored `output/41a-step6/check_workflow.py` and its JSON output.
- **Step 6 browser check:** the fresh local preview shows the corrected source
  note. All four player API requests returned 200; zero console errors.
  Screenshot: `output/41a-step6/source-note.png`.
- **Step 6 Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed with the API venv on PATH: 632 web tests, production build and 3,109
  API tests. Same non-failing warnings as Step 1. `git diff --check` passed.
- **Remaining external acceptance:** no commit, merge, push or GitHub dispatch
  was performed. The new workflow job must be tested with a manual dispatch
  after a separately approved push; downloading from a GitHub runner remains
  unverified. Local backfill and browser acceptance are proven above. The
  current ledger has only F-09 (P3) and F-12 (P2), both unverified; no open or
  fixed P0/P1 findings block the local review handoff.

## Files / areas

- New: `api/app/core/tennismylife.py`, `api/app/ingest/tennismylife.py`,
  `api/tests/test_tennismylife.py`
- Changed:
  - `api/app/core/box_score_join.py`
  - `api/app/repositories/player_match_stats.py`
  - `api/app/repositories/players.py`
  - `api/app/repositories/matches.py`
  - `api/app/repositories/props.py` (source filter only)
  - `api/app/services/tennis/player_detail.py`
  - `api/tests/test_box_score_join.py`, and possibly
    `api/tests/test_box_score_candidates.py`
  - `.github/workflows/tennis-ingest.yml`
  - `AGENTS.md`

## Data / contracts

- **No migration.**
- **`player_match_stats.source = 'tennismylife'`** (load-bearing; 41b reads
  its history from the CSVs, not this table, but later readers filter on it):
  - `source_match_key` is `sha256("tml-v1|tourney_id|round|opponent")`,
    stable across the ongoing and yearly files.
  - `match_date` is TennisMyLife's `tourney_date`.
  - `score` is winner-first, as TennisAbstract stores it.
  - Rows are stored only with stats.
- **`get_box_score_candidates(..., sources=...)`** (load-bearing): the default
  is TennisAbstract only. A new reader opts in to `tennismylife` explicitly.
  Grading readers stay on the default until a reviewed change says
  otherwise.
- **Precedence rule in `join_box_score`** (load-bearing): a TennisAbstract
  row with stats always wins, and TennisMyLife fills gaps only.
- **Upstream file shape:** Sackmann columns (`tourney_id`, `tourney_name`,
  `surface`, `tourney_date`, `winner_name`, `loser_name`, `score`, `round`,
  `w_ace`, `w_df`, `w_SvGms`, `w_bpSaved`, `w_bpFaced`, the same `l_*`
  columns, and so on). The parser fails loudly when a required column is
  missing.

## Testing

- **Test gate on.** Logic tests:
  - the parser (step 1)
  - the join precedence (step 3)
  - name resolution (step 4)
- **Not unit-tested:** the SQL source filter, the CLI's network calls and the
  workflow. These are proved by fixed-input CLI diffs against `master`
  (steps 2 and 5), the dry-run and real-run counts, a page check of one gap
  match, and the dispatch run.
- **Final gate:** Verify, `npm --prefix web run verify && cd api && python -m
  pytest`, with the API venv active.

## Notes for the AI

- `app/core/` stays pure: the parser and `resolve_name` take data, not a
  session or a URL. Normalize names with `normalize_name` in the ingest (a
  repository helper) and pass the normalized string into core.
- Every SQL statement lives in repositories. Batch: one index load per run,
  one upsert per chunk, never a query per row.
- Writes go to the shared Neon database. A dry run is free; the first real
  run and the `--since 2026-01-01` backfill each need an explicit owner yes in
  chat.
- Don't touch `box_score_key` or TennisAbstract's key formula (migration
  `0038` depends on it).
- TennisMyLife flags its WTA files as less reliable. Precedence keeps
  TennisAbstract authoritative wherever it has stats, so WTA rows only fill
  gaps. Note the WTA disagreement rate in the run summary if any shows up in
  step 5's check.
- The interview guide (`docs/SportApp-Employer-Interview-Guide.md`, local and
  untracked) gets a data-source line at `/complete` if the file exists.
- No em dashes in code comments, docs or commit messages.

## Completion review, 2026-10-20

- Final safety pass and invariants review: clean. Core remains pure, SQL stays
  in repositories, grading defaults to TennisAbstract, and only the three
  display calls opt in to TennisMyLife. No model, version, fit, held-out
  evaluation, signal-color, admin-security or Render request-path change.
- Exact Verify command passed in this session after the final source edits:
  `npm --prefix web run verify && cd api && python -m pytest` (API venv on PATH),
  with 632 web tests, production build and 3,109 API tests passing.
- No shared Blueprint skill behavior changed; neither adapter tree changed.
  Existing F-09 (P3) and F-12 (P2) remain unverified in the ledger; no resolved
  findings are archived with 41a, and no open/fixed P0/P1 blockers exist.
- The build-plan wording now records display-only gap filling and unchanged
  grading, matching the approved spec. Parent 41 stays open for 41b/41c.
  The overview was refreshed from both plans, retaining the prior planning
  refresh and distinguishing local implementation from hosted deployment.
- The local, ignored employer interview guide was updated with the source,
  precedence, idempotency and unchanged-grading evidence. It is never staged.
- Manual try: run the API and web with the documented dev commands, open
  `/#/tennis/player/2025` and `/#/tennis/match/84221`, and find Svitolina's
  September 27 match versus Noskova: six aces and three DFs in both places.
  CLI preview: `python -m app.ingest.tennismylife --dry-run` from `api/`.
- Owner approved local completion with the unchecked post-push acceptance
  item above deferred until a separately approved push. No remote dispatch
  or deployment is implied by this archive. Merge approval is still pending.
