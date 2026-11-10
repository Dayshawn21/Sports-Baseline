# Current Feature

## Tennis ELO shadow: freeze after each odds refresh

**Type:** Fix
**Branch:** `fix/tennis-shadow-cadence` (worktree `.claude/worktrees/fix-tennis-shadow-cadence`)
**Status:** Complete 2026-11-09 (Step 1). Step 2 is runner acceptance:
partly met as of 2026-11-10, see "Runner results". An odds-triggered freeze
has run its step but has not yet inserted a pair.

## Completion evidence (2026-11-09)

- Workflow parse (PyYAML): triggers `schedule`, `workflow_run` (`Tennis Game
  Odds`, `completed`), `workflow_dispatch`. The predictions job's `if` is
  unchanged, so it is skipped on `workflow_run`. The freeze job adds the
  `workflow_run` success branch. The restore step has `id: elo-inputs`, and the
  freeze step is gated with `github.event_name != 'workflow_run' ||
  steps.elo-inputs.outputs.cache-hit == 'true'`.
- Verify in the worktree: web typecheck and build passed; web tests 1337/1337;
  API `pytest` 6043 passed (CI's dummy `DATABASE_URL`, since a worktree has
  no `api/app/.env`).
- Baseline to compare Step 2 against: on 2026-11-09, `tennis_elo --count`
  read v3 frozen ATP 0, WTA 2, ATP_CHALLENGER 9. The 2026-11-08 freeze run
  `42510003746` paired 8 of 134 attempts.

## Runner results (through 2026-11-10)

Freeze runs since the push (UTC):

| Created | Trigger | Run | Freeze step | Attempts | Paired | Inserted |
|---|---|---|---|---|---|---|
| 11-09 15:28 | odds `42644910284` (dispatch) | `42645055411` | skipped, cache miss | n/a | n/a | n/a |
| 11-09 18:42 | odds `42676256759` | `42676365593` | skipped | n/a | n/a | n/a |
| 11-09 23:05 | 13:30 cron | `42717561445` | ran | 114 | 36 | 36 |
| 11-10 02:40 | odds `42744328367` | `42744406654` | skipped | n/a | n/a | n/a |
| 11-10 12:29 | odds `42816165302` | `42816250676` | skipped | n/a | n/a | n/a |
| 11-10 20:32 | 13:30 cron | `42896237939` | ran | 84 | 23 | 23 |
| 11-10 21:46 | odds `42908195789` | `42908308918` | ran | 84 | 0 | 0 |

Run `42908308918` reasons: `already_started` 31, `already_frozen` 24,
`not_unstarted` 17, `missing_market` 5, `missing_or_invalid_candidate` 4,
`missing_incumbent` 2, `ambiguous_players_or_group` 1. Every match that could
be paired had been paired by the 20:32 cron.

The box-score job wrote the day's ELO cache at 21:11 on 11-09 (run
`42700193490`) and 18:22 on 11-10 (run `42874541221`), later than the 16:45
this spec assumed. On 11-09 no odds run landed after it.

`tennis_elo --count` at 2026-11-10 22:55 UTC: v3 frozen ATP 8, WTA 3,
ATP_CHALLENGER 59, total 70, which is the baseline 11 plus 36 and 23. Mature 0;
no outcomes read.

Against the Step 2 list:

- Odds run triggers a freeze run: met (`42644910284` to `42645055411`).
- Early run skips on a cache miss: met (`42645055411`).
- Evening odds run shows paired and inserted pairs: **not met**. The step ran
  in `42908308918` without error and inserted 0.
- Frozen counts above about 8 a day: 36 and 23, but both came from the 13:30
  cron path, so this does not show the odds trigger adding pairs.

## The problem

The 41b forward comparison (`tennis-elo-source-v3`, first eligible UTC day
2026-11-07) is collecting pairs, but slowly. It freezes once a day, in
`tennis-predictions.yml` after the 13:30 UTC cron, and GitHub starts that cron
4.5 to 7 hours late (18:09 and 18:26 UTC on 11-07 and 11-08). Of the 134
attempts on 11-08, 8 were paired:

| Reason | Attempts |
|---|---|
| `missing_market` | 63 |
| `already_started` | 30 |
| `missing_incumbent` | 17 |
| `not_unstarted` | 12 |
| `paired` | 8 |
| other | 4 |

`tennis_elo --count` on 2026-11-09 read ATP 0 frozen, WTA 2, Challenger 9. At
about 8 pairs a day across three groups, each needing 300, 41c has no verdict
in sight.

Two of the causes are timing, not data:

- **Already started.** The freeze sees today's and tomorrow's UTC matches, but
  only once, late in the day, so the day's earlier matches have begun.
- **Missing market.** `tennis-odds.yml` prices the next 14 hours. A freeze
  that runs before the evening odds refresh misses tomorrow's early prices.

## The fix

Run the shadow freeze again each time `Tennis Game Odds` finishes, so a freeze
follows every price refresh. The evening odds run (about 20:00 UTC) prices
tomorrow's early matches, and a freeze right after it catches them before they
start, under today's candidate snapshot.

- Add `workflow_run` on `Tennis Game Odds`, `types: [completed]`, to
  `tennis-predictions.yml`. Only the freeze job runs on it; the predictions
  job's `if` already restricts it to the 13:30 schedule or a dispatch, so it
  is skipped.
- The freeze job also runs when the event is `workflow_run` and the odds run
  concluded `success`, even though `needs: predictions` was skipped.
- **On a `workflow_run` trigger, freeze only when today's candidate inputs
  are cached** (`cache-hit == 'true'` on the restore step). The box-score job
  writes them about 16:45 UTC, so morning odds runs skip cleanly. Without this
  gate, a pre-snapshot cycle would record coverage attempts with the candidate
  missing for matches that today never enter the denominator (they are
  `already_started` by the one late freeze), which would lower measured
  coverage for a reason that is only workflow timing. The 13:30 run keeps
  today's behavior, recording a miss when the day's inputs never arrive, so a
  day with no candidate still shows in coverage.
- The existing `tennis-elo-shadow-freeze` concurrency group keeps runs
  serial.

### Why this stays inside the pre-registered rule

- The 41b rule pins the start, population, gates, sample, coverage and
  verdict. It does not pin how often a cycle runs. It already allows repeated
  cycles: "First successful pair wins; duplicate dispatches do nothing", and
  coverage counts "recovery after an earlier missing source".
- The code already supports it: `cycle_key` is the start hour, the cycle table
  is keyed `(experiment_version, cycle_key)`, and a reused hour inserts
  nothing. Pairs are unique per `(match_id, experiment_version)`.
- No outcome has been read. Count mode selects no winner or score columns, so
  this change is made outcome-blind.
- The experiment JSON, its hash, the code, the migrations and the rule are
  unchanged, so v3 continues; nothing restarts.

### Must not break

- The daily predictions and prop snapshot run (13:30 cron, unchanged).
- The 13:30 freeze path, including its cache-miss behavior.
- Manual dispatch of either job.
- `--scheduled` still skips before the first eligible day and on an inactive
  experiment.

### Out of scope

- Moving the box-score / candidate snapshot earlier in the day (the pairs
  lost before about 16:45 UTC stay lost).
- The `missing_incumbent` share, which is production prediction coverage.
- Any change to the rule, code, experiment JSON or count report.

## Build steps

- [x] **Step 1 - Trigger the freeze after each odds run.** In
  `.github/workflows/tennis-predictions.yml`:
  - add the `workflow_run` trigger;
  - widen the freeze job's `if` to include a successful `workflow_run`;
  - give the cache restore step an `id`, and on `workflow_run` gate the
    freeze step on `cache-hit == 'true'`;
  - update the header comments.

  Update the `docs/tennis-actions.md` row for this workflow ("Daily 13:30;
  freeze also after each Tennis Game Odds run").

  **Done when:**
  - The YAML parses. On a `workflow_run` event, the expressions resolve to
    predictions skipped and the freeze job running, with the freeze step
    gated on a cache hit; schedule and dispatch resolve exactly as before.
    Shown by a diff of the `on:` and `if:` blocks and a parse check.
  - Verify passes.

- [ ] **Step 2 - Runner acceptance (after merge and push, each needing its
  own yes).**
  - The first odds run after the push triggers a freeze run.
  - A run before about 16:45 UTC shows the freeze step skipped on a cache
    miss.
  - The evening odds run shows `Attempts ... paired: N` and
    `WRITE: N inserted`.
  - `tennis_elo --count` the next day shows frozen counts above the
    once-a-day rate (about 8 a day).

  **Done when:** those run IDs and counts are recorded here.

## Verify

- Step 1: a parse check of the workflow, the diff, and Verify
  (`npm --prefix web run verify && cd api && python -m pytest`). No logic
  changes, so no new test.
- Step 2 (production): `gh run list --workflow tennis-predictions.yml` shows
  `workflow_run` runs after odds runs. The evening run's freeze log shows
  inserted pairs. `python -m app.backtest.tennis_elo --count` shows the daily
  frozen count rising.
- Workflows register only when a push changes their file, so Step 2 can only
  be checked after a push to `master`.
