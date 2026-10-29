# Feature: Forward prop check

**From build-plan:** feature 48e
**Status:** not started (spec awaiting review; open questions decided 2026-10-29)

## Goal

Pre-register, before any `props-v3` or later snapshot is graded, the one rule
that decides which tennis PrizePicks slices may ever be ranked by P(over), then
build the read-only grader that applies it. A slice is stat x tour x anchor
(book or model total) x payout (standard, goblin, demon) x side. Each slice
reads **adopt** or **hide**; a reject is final for that projection version.
48g ranks only adopted slices, so this rule is the gate between "gray
reference number" and "pick".

The rule is written blind: no `props-v3` (or `props-v4`) line outcome is read
while writing it or before it is committed.

## In scope

- **The rule, as a pure module** (`app/core/tennis_prop_check.py`), committed
  as its own checkpoint before the grader can run. It reuses the shared 27i
  rule in `app/core/prop_ranking_rule.py` unchanged: `pick_side`
  (`MIN_PICK_MARGIN` 0.03 over break-even), `one_pick_per_bet` (ladder rungs
  are one decision), `verdict_sample` (`MIN_PICKS` 200 across `MIN_PERIODS` 4,
  fixed once filled) and `SliceResult`. Tennis adds only what 27i lacks: the
  slice key, the period, push handling, exclusions, and a 3 SE gate in its own
  `tennis_slice_verdict` (27i's `slice_verdict` hardcodes 2 SE, and the shared
  constant must not move; see decision 2).
- **Settlement of frozen lines** with the existing tennis settlement code
  (`resolve_actual`, `settle`, `is_completed_score`, the box-score join), the
  same path `app/backtest/tennis_prop_snapshots.py` uses.
- **A repository read** of the latest pre-start snapshot per line with the
  fields the rule needs (P(over), P(under), P(push), market total, flags,
  start time, tour inputs), reusing the existing pre-start eligibility SQL.
- **A read-only CLI** `python -m app.backtest.tennis_prop_check
  [--version props-v3] [--as-of YYYY-MM-DD]` that prints the funnel,
  exclusions, and every slice's state. Undecided slices show sample size and
  weeks only, never a running hit rate.
- **Version-agnostic by construction:** the rule reads only columns every
  snapshot version stores, and takes the version as an argument. It applies
  as written to `props-v3` and to whatever version 48c ships (`props-v4` per
  its spec), each graded as its own sample and never pooled.
- Docs: one line each in `AGENTS.md` (Ingest/backtest commands) and
  `docs/commands.md`.

## Out of scope

- **48c's files** (`app/core/tennis_match_sim.py`, `tennis_match_chain.py`,
  `app/backtest/tennis_match_sim.py`, `app/ingest/prop_snapshots.py`,
  `app/services/tennis/prop_snapshots.py` and their tests). 48e only imports
  `PROJECTION_VERSION` as the CLI default.
- Ranking, picking or coloring anything (48g). No router, schema or web change;
  the prop board stays gray.
- The `/tennis/model` track record page. Showing 48e verdicts there is 48g's
  or a later item's call.
- Sportsbook player props (48d).
- Running the grader against the real database. That is the owner's call
  after the rule is committed (see Notes).
- Any change to projection, P(over), push or EV math, or to the shared 27i
  constants. Changing any 48e constant later means a new rule name and a new
  sample, never a re-read.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [ ] **Step 1 - Register the rule** - `app/core/tennis_prop_check.py`, pure:
  the constants and functions under "The pre-registered rule" below
  (`TennisFrozenLine`, `slice_key`, `period_of`, `finished_periods`,
  `to_frozen_call`, `check`), built on `prop_ranking_rule` without editing it.
  Tests in `api/tests/test_tennis_prop_check.py` on synthetic lines only: push
  exclusion and push-excluded probabilities, anchor at 16.5 / 17.0 / None,
  tour labels (WTA 125 from a CHALLENGER match with WTA players), week
  boundaries (Sunday 23:59 UTC vs Monday 00:00) and the 3-day maturity, each
  excluded flag, dedupe-before-slice (a ladder whose rungs straddle anchors
  counts once, in the surviving rung's slice), adopt / reject / insufficient
  on a constructed slice (one at 2.5 SE above break-even must read reject,
  one at 3.1 SE adopt), and that an empty slice list is not "passed".
  *Done when:* `pytest tests/test_tennis_prop_check.py` passes, the module
  imports nothing from `app.db`, `app.repositories` or `app.services`, and
  `git diff master -- api/app/core/prop_ranking_rule.py` is empty. **Commit
  this step as a checkpoint before Step 2:** the commit is the
  pre-registration.
- [ ] **Step 2 - Settle frozen lines** - in the same core module (or
  `app/core/tennis_prop_check_settle.py` if Step 1's file passes ~200 lines),
  a pure `to_frozen_line(row, join)` that turns one snapshot row plus its
  box-score join into a `TennisFrozenLine` with `outcome` over / under / push
  or the exclusion reason (`incomplete_score`, `not_settleable`, the join
  reason), via `resolve_actual` and `settle`. *Done when:* tests cover a
  settled over, a whole-number push, a retirement score, an ace line with and
  without a join, and match the outcome the existing 26f grader gives on the
  same synthetic row.
- [ ] **Step 3 - Repository read** - `get_prop_check_snapshots(db, version)`
  in `app/repositories/prop_snapshots.py` returning a new frozen dataclass
  `PropCheckSnapshot`: the existing `get_graded_prop_snapshots` fields plus
  `start_time`, `p_over`, `p_under`, `p_push`, `market_total_games`,
  `data_quality_flags`, `match_tour` and both players' `tour`. Same
  `DISTINCT ON` latest-pre-start rule and `_captured_prestart_sql` filter; the
  existing function is untouched. *Done when:* a repository test in the style
  of `test_prop_snapshot_repository.py` asserts the SQL keeps the pre-start
  filter, the version parameter and the completed-match filter, and builds a
  `PropCheckSnapshot` from a sample row.
- [ ] **Step 4 - Grader CLI** - `app/backtest/tennis_prop_check.py`: loads
  snapshots and box-score joins (as `tennis_prop_snapshots._main` does),
  builds frozen lines, runs `check`, prints the report described under
  Data / contracts. Pure `report(...)` is tested on a synthetic `CheckResult`.
  Add the command to `AGENTS.md` and `docs/commands.md`. *Done when:*
  report tests pass (an undecided slice prints no hit rate; a decided slice
  prints hit rate, SE, lower bound, break-even and adopt or hide; the
  expected-false-adopt line appears), `python -m app.backtest.tennis_prop_check
  --help` runs, and Verify passes.

## Files / areas

- New: `api/app/core/tennis_prop_check.py`, `api/app/backtest/tennis_prop_check.py`,
  `api/tests/test_tennis_prop_check.py`, `api/tests/test_tennis_prop_check_report.py`
- Changed: `api/app/repositories/prop_snapshots.py` (new function and
  dataclass only), `api/tests/test_prop_snapshot_repository.py`,
  `AGENTS.md`, `docs/commands.md`
- Read, not changed: `app/core/prop_ranking_rule.py`, `app/core/prop_settlement.py`,
  `app/core/tennis_format.py` (`display_tour`), `app/core/prop_projection.py`
  (`normalize_stat_type`), `app/routers/props.py` (the 17.0 anchor threshold)
- No migration.

## Data / contracts

### The pre-registered rule (load-bearing, frozen at Step 1's commit)

| Part | Rule |
|---|---|
| Name | `TENNIS_PROP_CHECK_RULE = "tennis-props-check-v1"`, registered 2026-10-29 |
| Unit | One snapshot row: the latest pre-start snapshot of a line (player, match, stat, odds type, line), as `get_graded_prop_snapshots` already selects |
| Version | Graded per `projection_version`; never pooled. A rule constant change is a new rule name |
| Stat | `normalize_stat_type(stat_type)` |
| Tour | `display_tour(match.tour, p1.tour, p2.tour)`: `ATP`, `WTA`, `CHALLENGER`, `WTA 125` (anything else is its own label, graded the same way) |
| Anchor | `book` when `market_total_games >= 17.0` (the threshold `routers/props.py` uses for `projection_source = market_total`), else `model`. Applies to every stat, totals-dependent or not |
| Payout | `odds_type` lower-cased; `standard`, `goblin`, `demon`; anything else excluded as `unknown_odds_type` |
| Side | `pick_side` from 27i: standard may be over or under, goblin and demon over only; a side is a pick only at break-even + 0.03 |
| Probabilities | Push-excluded: `p_over / (1 - p_push)` and `p_under / (1 - p_push)`, matching what 48f shows. Missing any of the three, or `p_push >= 1`, excludes the line as `no_probability` |
| Break-even | `BREAK_EVEN_BY_ODDS_TYPE` (Power 2-pick basis: 57.7%, 75.8%, 41.3%). No Flex gate (decision 1) |
| Outcome | Settled by the 26f path. Push excluded (`push`). Retirement, walkover or bad score excluded. Box-score stats with no join excluded with the join reason |
| Excluded flags | `match_finished`, `match_link_invalid`, `bo5_unsupported_stat`, `unsupported_stat`, `ungraded_stat`, `missing_player`, `missing_match`. Every other flag (`no_market_total`, `small_sample`, `stale_stats`, `missing_stats`, 48c's `no_market_moneyline`, `sim_level_unverified`, ...) is graded, never split on |
| Period | ISO week of `start_time` (Monday 00:00 UTC). A week counts only once `as_of >= Monday + 7 + 3 days` (`TIER_MATURITY_DAYS` reasoning: late box scores) |
| Dedupe | `one_pick_per_bet` across all picks first; the surviving rung's own tour and anchor assign its slice, so one decision is never counted twice |
| Slice | (stat, tour, anchor, odds_type, side) |
| Verdict | `tennis_slice_verdict` per slice: `verdict_sample` fixes the first whole weeks holding 200 picks across 4 weeks; adopt when hit rate - 3 SE > break-even (`TENNIS_STANDARD_ERRORS_REQUIRED = 3.0`), else reject. No sample yet reads insufficient |
| Reading | adopt -> **adopt**; reject or insufficient -> **hide**. A reject is final for that version and rule |

Exports 48g depends on (load-bearing): `TENNIS_PROP_CHECK_RULE`,
`TennisFrozenLine`, `slice_key(line) -> TennisSlice`, `TennisSlice`
(a `NamedTuple` of stat, tour, anchor, odds_type, side), `check(lines, as_of)
-> CheckResult` with `slices: dict[TennisSlice, SliceResult]` and
`adopted(result) -> frozenset[TennisSlice]`. 48g must compute a live line's
key with the same `slice_key` and the same exclusions.

### CLI report shape

```
Tennis forward prop check - tennis-props-check-v1 on props-v3 (as of 2026-11-30)
  frozen rows 4210 | excluded: push 61, no_probability 12, incomplete_score 40, ...
  calls 3890 | picks 1204 | bets 870 | finished weeks 5
  decided slices 2 | expected false adopts at 3 SE: 0.003
  stat         tour   anchor odds     side   n   weeks  hit    SE    lower  b/e    reads
  aces         ATP    book   standard over   212 5      61.8%  3.3%  51.9%  57.7%  hide (reject, final)
  total_games  WTA    book   standard under  67  3      -      -     -      57.7%  hide (insufficient)
```

## Testing

- Steps 1 and 2: unit tests on pure functions, synthetic lines, fixed
  dates (`as_of` passed in, never the clock). Includes a test that a
  constructed slice of 200 picks over 4 weeks at a known hit rate gives the
  expected adopt or reject, and that adding a later week never changes it.
- Step 3: repository test with the session mocked, as the existing snapshot
  repository tests do.
- Step 4: report formatting tests on a synthetic result; no database.
- No React change, so no web test; Verify still runs both halves.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Blind rule.** Do not query `prop_projection_snapshots` joined to outcomes,
  run `app.backtest.tennis_prop_snapshots`, or open the track record for any
  v3 or v4 data while building. Tests use synthetic rows only. This container
  has no database anyway; keep it that way for this feature.
- **Step 1's commit is the registration.** Nothing in Steps 2-4 may change a
  Step 1 constant. If one looks wrong during the build, stop and ask; the fix
  is a new rule name, decided before any grading.
- **First real run** is the owner's, after merge, and needs a separate yes in
  chat. Because the verdict sample is fixed by count, not by result, repeat
  runs are not repeated tests; the report still hides undecided hit rates so
  nobody is tempted to retune on a running number.
- Core purity: `app/core/tennis_prop_check.py` takes rows in, returns results;
  the CLI owns the session. Repositories own SQL.
- Do not edit `prop_ranking_rule.py` or `prop_ranking_check.py`; NFL and NBA
  verdicts depend on them. Tennis's own `to_frozen_call` lives in the new
  module because 27j's version gates on NFL-style model and P(over) versions.
- Do not touch 48c's files (Out of scope). If 48c lands first and renames its
  version, nothing here changes: the CLI takes `--version`.
- No em dashes in new code, docs or commit messages.
- Employer interview guide: at `/complete`, if `docs/SportApp-Employer-Interview-Guide.md`
  exists locally, add that tennis props now have a pre-registered forward
  check (registered, not yet graded). Never stage it.

## Decisions (owner delegated them to the AI, 2026-10-29)

1. **Power only, no Flex gate.** Every break-even and EV the app shows is the
   2-pick Power basis, so the gate matches what the board displays. Flex
   break-evens change with entry size, and PrizePicks publishes no goblin or
   demon Flex multipliers, so a Flex gate would mean pre-registering numbers
   we made up. A Flex gate can come later as a new rule name.
2. **3 SE, not the plan's 2 SE.** 27j's 2 SE was set for 4 NFL slices. Tennis
   has hundreds (stat x tour x anchor x payout x side), and at 2 SE each
   decided slice has about a 2.3% chance of a false adopt, so a few dozen
   decided slices would likely adopt at least one on noise. The costs are
   lopsided: a missed adopt keeps a line gray, a false adopt ranks it and
   invites real bets. 3 SE (about 0.1% each) keeps the whole family near a
   5% chance of any false adopt. The price is a higher bar: a standard slice
   of 200 needs roughly a 68% hit rate against 57.7%, so few slices will
   adopt, and that is the honest outcome at this sample size. The build-plan
   line says 2 SE; `/complete` records this deviation in the archive and
   offers the one-word plan edit for your approval.
3. **Grade `no_market_total` lines in their `model` slice.** You asked for the
   anchor split, and grading is the only way to learn whether Challenger and
   WTA 125 lines (no book total) carry any edge. Grading never makes a pick:
   48a's "never a pick without a book total" stands unless that exact slice
   adopts, at the 3 SE bar. Excluding them would make that rule permanent
   without ever testing it.
4. **ISO week as the period.** Tennis draws run weekly, so 4 weeks means at
   least 4 different tournament weeks. With snapshot days, 4 periods could
   be 4 rounds of one event, with the same players, surface and conditions,
   which is far less independent evidence than the 4-period floor is meant
   to guarantee. It also matches NFL's week period in 27j.
