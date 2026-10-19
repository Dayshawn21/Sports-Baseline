# Best-pick prop cards use the board's prop assessment

**Type:** Fix
**Fixes:** F-04, F-05 (archived as `nfl-finished-week-stats/F-04` and
`nfl-finished-week-stats/F-05`, accepted 2026-10-18 pending this repair; the
ledger says to fix them together because they share one root cause). Carried
into the live ledger as F-17 and F-18.
**Branch:** `fix/tennis-best-pick-prop-parity`

## The problem

Best-pick prop cards (`generate_prop_picks`,
`api/app/services/tennis/best_picks.py:211`) re-derive each PrizePicks prop's
side, probability and tier instead of using the board's assessment (`_enrich`,
`api/app/routers/props.py:228`), which is also what the 26f `props-v2`
snapshots store (`enrich_props`). The copy has drifted in two ways.

**F-04: guards the cards skip.** The board blanks or caps a row that the card
path still promotes:

| Board guard (`_enrich`) | Card path |
|---|---|
| Hard block: `match_link_invalid`, `match_finished`, `bo5_unsupported_stat`, `unsupported_stat`, missing player, match or stats | Only checks player, line and stats |
| Cap at LEAN: `stale_stats`, `small_sample`, `ungraded_stat` | `small_sample` flag only on priced rows; no cap |
| Downgrade one tier: `missing_opponent_stats`, `missing_prediction` | None |

The audit's synthetic run: aces 5.5 with an invalid match link is no row on the
board but OVER LOCK on a card; the same line on 2020 stats is OVER LEAN
`stale_stats` on the board but OVER LOCK on a card; BO5 Total Sets 3.5 is
blocked on the board but UNDER LOCK on a card (from a 2.5-set projection).

**F-05: different probability and tier.** For the same mean, stats, opponent,
win probability and line:

- Cards call `prop_over_under_probs` without `best_of` or the deciding-set
  probability, so total games uses the marginal BO3 normal instead of the
  board's format-aware mixture.
- Cards use the unconditional side probability; the board conditions on no
  push (`decision_probability`, and `p_over / (1 - p_push)` for goblin and
  demon).
- Unpriced cards tier with `confidence_tier(prob)`; the board uses
  `assess_prop`, EV against the payout table.

| Case | Board / snapshot | Card |
|---|---|---|
| BO3 total games, mean 22.5, line 25.5, win prob .55 | UNDER .626, LEAN | UNDER .6929, STRONG |
| Goblin aces 9.5, mean about 10.85 | OVER .643, PASS | OVER .6429, STRONG |

The goblin card is below the 75.76% break-even yet shown STRONG. So
`/tennis/model/prop-tiers` grades a tier the cards do not actually show.

## The fix

Cards consume the board's `PropLine` for each PrizePicks prop, rather than
recomputing it.

- **One mapping from inputs to `PropLine`.** Extract the list comprehension in
  `_enrich_props` into a pure helper, e.g. `enrich_with(props, opponent_ids_map,
  rolling_stats, prediction_probs, market_probs, market_total_games)`, which
  `_enrich_props` calls. The best-picks route (`app/routers/tennis.py:520`)
  already loads every one of those inputs, so it calls the same helper on the
  `get_today_props` rows inside its `assemble()` worker thread. No extra query,
  and the board's win-probability precedence (prediction, else market) is the
  same one the route uses today.
- **`generate_prop_picks(pred, prop_lines)`** takes those `PropLine`s for the
  match and makes a card only when the board row has a `recommendation` and a
  `confidence` other than `PASS`, keeping the first-set exclusion (16e). The
  card shows the board's side, `hit_probability` (as `model_prob`),
  `confidence` and `data_quality_flags`. `edge_pct`, `stat_avg` and
  `matches_count` feed the existing reasoning text and `_score_pick`. EV and
  Kelly are carried only when the row has a real side price: the board's
  PrizePicks EV is against assumed payouts, and cards have always shown those
  lines as unpriced (`test_unpriced_picks_leave_ev_pct_none`).
- `bankroll_builder.py` imported `_serve_hold` through `best_picks`; it now
  imports `serve_hold` from `app.core.prop_projection` directly.
- **`build_best_picks`** passes `prop_lines` through to `generate_prop_picks`.
  Match-odds rows (`get_today_match_odds_as_props`) still go, unchanged, to
  `generate_market_odds_picks` as raw `Prop`s.
- Remove what the card path no longer uses (its `games_won_probs`,
  `prop_over_under_probs`, `confidence_tier` and `assess_bettable_pick` calls,
  if nothing else in the module needs them).

**Must not change:**

- The board, `/tennis/props/*` responses and `props-v2` snapshots: `_enrich` is
  untouched, so no `PROJECTION_VERSION` bump. Prove snapshots unchanged with the
  existing snapshot tests.
- Moneyline best picks stay off (`MONEYLINE_PICKS_ENABLED = False`); derived,
  serve-edge and market-odds picks are unchanged.
- No probability, distribution, payout or tier threshold changes. Cards only
  stop disagreeing with the board; the expected visible effect is fewer and
  lower-tier prop cards.
- `_enrich` stays in `app/routers/props.py` (moving it to a service is
  deferred, per the comment on `enrich_props`).

**Out of scope:** F-05's suggestion to show prop cards without signal color
until the `props-v2` tier verdict lands. That is a display decision for the
owner; raise it at review, not in this diff.

## Build steps

1. [x] **Cards read the board's assessment.** The helper extraction, the
   route change, the new `generate_prop_picks`/`build_best_picks` signatures,
   and tests in `api/tests/test_best_picks.py`. Rework the existing prop tests
   (`test_bo5_games_won_prop_uses_match_format`,
   `test_first_set_props_are_no_best_pick_until_graded`) onto `PropLine`
   inputs built by `_enrich`, and add parity regressions that run one input
   through `_enrich` and then the card path:
   - invalid match link, finished match, BO5 total sets: no card
   - stale stats, small sample: card at most LEAN, flags carried
   - missing opponent stats, missing prediction: card one tier below the
     un-downgraded tier
   - BO3 total games (mean 22.5, line 25.5, win prob .55): card probability and
     tier equal the board's (.626, LEAN)
   - goblin aces 9.5 below break-even: no card
   - integer line with a push: card probability is the board's push-conditioned
     one
   - first-set stat: still no card

   **Done when:** every card's side, `model_prob`, `ev_pct`, confidence and
   flags equal the board row it came from in those tests; the existing
   snapshot tests pass unchanged; Verify passes.

2. [x] **Repair F-19 - unused imports in files this fix touched.** Delete
   `_serve_hold` from `bankroll_builder.py`, and `MIN_EV` and
   `_expected_total_games` from `best_picks.py`.

   **Done when:** nothing reads the three names and Verify passes.

## Verify

- **Tests:** `npm --prefix web run verify && cd api && python -m pytest` (the
  Verify command, API venv active).
- **Live parity check:** with the local API running, for today's slate, every
  prop pick in `GET /tennis/predictions/best-picks` matches a row in
  `GET /tennis/props/prizepicks` with the same player, stat, line and odds type,
  and the same side, hit probability (to 3 dp), EV and confidence. No card comes
  from a board row with no recommendation or a `PASS` tier.
- **UI:** the tennis slate's best-pick prop entries show tiers no higher than
  the prop board's for the same line.

## Notes

- `fix/tennis-board-moneyline-reference` (F-03, commit `d657d4f`) is not yet
  merged to `master`. Merge it first, then branch this fix from `master`; it
  touches `best_picks.py`'s neighbourhood but not the same lines.
- `blueprint/build-plan.md` and `project-overview.md` carry uncommitted item-39
  edits; leave them as found.

## Completion evidence, 2026-10-18

- Dependency F-03 was squash-merged locally to `master` as `a0776fb` before this completion. Its fresh Verify passed: 611 web tests, 2,610 API tests, production build.
- This fix's exact Verify command, `npm --prefix web run verify && cd api && python -m pytest`, passed with the API venv on PATH: 611 web tests, 2,620 API tests, production build. Used the password-free CI database URL; no test connects. One existing Starlette/AnyIO deprecation warning. Logs: local ignored `output/prop-parity-verify.log`.
- Behavioral evidence carried from the implementation and audit: on the 2026-10-18 local slate, all 10 player-prop cards matched their board row. The parity regressions cover hard blocks, caps, missing-input downgrades, format-aware probability, pushes and goblin break-even. Snapshot tests passed without changing `_enrich` or `props-v2`.
- UI consumer review: `displayedBestPicks` in `web/src/utils/unifiedTennis.ts` suppresses duplicate prop cards where board rows exist. Remaining cards use the same assessed probability and tier. No frontend change in this fix.
- Invariants review: clean for this diff. Moneylines remain disabled; enrichment stays in the worker thread using already-loaded inputs; no SQL, core math, fit artifact, rule, version or projection change.
- Focused quality audit closed F-19; F-17 and F-18 retain their earlier closed verdicts. New F-20 is a pre-existing unused `field` import in `bankroll_builder.py`, P3 and nonblocking. Unresolved findings stay in the live ledger.
- Item-39 planning edits and reference files remain outside this fix. The local ignored employer guide describes the shared-assessment repair as locally verified, without claiming deployment.

## How to try it

Start the API and web app using the commands in `AGENTS.md`. Compare the same player's stat and line on the tennis slate and prop board: a best-pick prop must not exceed the board's tier, and blocked or PASS rows must not produce cards. For the API path, compare `/tennis/predictions/best-picks` with `/tennis/props/prizepicks`; unpriced cards intentionally keep EV blank.

## Findings

### tennis-best-pick-prop-parity/F-17 [P1] closed - Best-pick props bypass the board's eligibility and data-quality gates (carried: nfl-finished-week-stats/F-04)

**File:** api/app/services/tennis/best_picks.py:210; api/app/routers/tennis.py:562; api/app/routers/props.py:780
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers); archived as `nfl-finished-week-stats/F-04` (accepted pending repair), carried here so its re-review is recorded with the repairing fix.
**Why it matters:** `generate_prop_picks` skipped `_enrich`'s hard blocks (invalid link, finished match, BO5 set counts), its LEAN cap (stale stats, small sample) and its missing-input downgrades, so cards showed OVER LOCK on lines the board blanked or capped.
**Suggested fix:** route cards through the board's assessment; add parity regressions for each guard.
**Resolution:** Fixed 2026-10-18 by `fix/tennis-best-pick-prop-parity` (step 1), awaiting /audit re-review. Cards now read the board's `PropLine` (`enrich_with`, the same mapping `_enrich_props` uses) and need a recommendation and a non-PASS tier. Parity tests in `test_best_picks.py` cover the three hard blocks, stale and small-sample caps, and both downgrades. Live 2026-10-18 slate: all 10 player-prop cards matched their board row.
Closed 2026-10-18 by /audit (scope: current; lenses: all). Re-review of the repaired code: `generate_prop_picks` (`best_picks.py:210`) has no path to a card without the board row's `recommendation` and a non-PASS `confidence`, and `_enrich` sets both to None on every PrizePicks hard block and applies the cap and downgrades before returning. The route (`tennis.py:562`) enriches only `get_today_props` rows; match-odds rows still reach `generate_market_odds_picks` unchanged. Non-PrizePicks player props cannot bypass the PrizePicks-only hard blocks: `get_today_props` returns null odds, and `leg_decimal_odds` gives an unpriced non-PrizePicks row no tier, so no card. The web renders prop cards only for matches with no prop rows (`displayedBestPicks`), so carrying board flags opens no new display path. 54 focused tests passed (best picks, live odds, prop snapshots, bankroll, prediction cache).
### tennis-best-pick-prop-parity/F-18 [P1] closed - Best-pick prop probabilities and tiers disagree with props-v2 snapshots (carried: nfl-finished-week-stats/F-05)

**File:** api/app/services/tennis/best_picks.py:210
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers); archived as `nfl-finished-week-stats/F-05` (accepted pending repair), carried here so its re-review is recorded with the repairing fix.
**Why it matters:** cards used a format-blind total-games probability, dropped push conditioning and tiered unpriced lines by raw probability, so a goblin below break-even could show STRONG and `/tennis/model/prop-tiers` did not grade the tier cards showed.
**Suggested fix:** cards consume the canonical probability, push handling and tier; no distribution or payout change.
**Resolution:** Fixed 2026-10-18 by `fix/tennis-best-pick-prop-parity` (step 1, same change as F-17), awaiting /audit re-review. Card `model_prob` and tier are the board's `hit_probability` and `confidence`. Tests: BO3 total games 25.5 is UNDER .617 LEAN on both (old card math about .674), an integer line is push-conditioned, a below-break-even goblin gives no card. `_enrich` and `props-v2` are unchanged, so no version bump. EV is carried only with a real side price, as before.
Closed 2026-10-18 by /audit (scope: current; lenses: all). Re-review: card `model_prob` is the board's push-conditioned `hit_probability` and its tier is the board's `assess_prop` tier, both computed by `_enrich` with the linked match's `best_of` and deciding-set probability. No distribution, payout or tier constant changed, and `_enrich`, `enrich_props` and `PROJECTION_VERSION` are untouched, so snapshot rows are unchanged (`test_prop_snapshots` passed). The win-probability precedence (prediction, else market) matches the route's former merge.
### tennis-best-pick-prop-parity/F-19 [P3] closed - Unused imports in files this fix touched

**File:** api/app/services/tennis/bankroll_builder.py:29; api/app/services/tennis/best_picks.py:16; api/app/services/tennis/best_picks.py:23
**Found:** 2026-10-18 by /audit (scope: current; lens: quality)
**Why it matters:** `coding-standards.md` says no unused imports. `bankroll_builder.py` never uses `_serve_hold`; this fix re-sourced the import from `app.core.prop_projection` instead of deleting it. `MIN_EV` and `expected_total_games as _expected_total_games` in `best_picks.py` were already unused on `master`.
**Suggested fix:** delete the three imports in this fix's branch; Verify confirms nothing else reads them.
**Resolution:** Fixed 2026-10-18 by `fix/tennis-best-pick-prop-parity` step 2, awaiting /audit re-review: the three imports are deleted, no module reads them, and Verify passed (611 web, 2,620 API tests, build green).
Closed 2026-10-18 by /audit (scope: imports and their consumers in `best_picks.py` and `bankroll_builder.py`; lens: quality). Re-read the changed imports and call sites, checked name loads with Python AST, and searched application and test callers: `_serve_hold` and `_expected_total_games` have no remaining consumer through these modules, and `best_picks.MIN_EV` is unused and removed. The separate `bankroll_builder.MIN_EV` remains used by its EV filter. No defect introduced by these removals. This focused pass does not claim security, performance or full test-quality coverage.
