# Feature: Calculators page

**From build-plan:** feature 61
**Status:** complete (2026-11-11)
**Branch:** `feature/calculators` (this worktree, `.claude/worktrees/calculators-273f37`)

## Goal

A `/tools` page with five betting calculators that run entirely in the browser:
odds converter, two-way no-vig fair odds, EV of a bet, fractional Kelly stake,
and PrizePicks power and flex entry EV. Every formula is a TypeScript port of a
pure function in `api/app/core/`, and one shared JSON fixture is asserted by
both pytest and Vitest, so the page and the API can never quietly disagree on
the same math.

## In scope

The five calculators, each a card on one page, with its formula source:

| Calculator | Inputs | Outputs | Python source (formula kept identical) |
|---|---|---|---|
| Odds converter | one value plus its format (American, decimal, implied probability) | the other two formats | `odds.american_to_prob`, `odds.american_to_decimal`, `odds.decimal_to_american`, `odds.prob_to_american`; decimal to probability is `prop_ev.break_even_probability` (1 / decimal) |
| No-vig fair odds | two American prices (side A, side B) | each side's fair probability and fair American price, the overround | `odds.implied_prob_from_american` (via `devig_two_way`), `odds.prob_to_american`, `odds.overround` |
| Expected value | fair win probability (percent), American price, optional stake | EV per unit as a percent, EV in stake units, break-even probability | `kelly.expected_value`; break-even from `prop_ev.break_even_probability(american_to_decimal(price))` |
| Fractional Kelly | fair win probability, American price, Kelly multiplier (Full, Half, Quarter presets, default Quarter = `DEFAULT_KELLY_MULTIPLIER`), optional bankroll | fraction of bankroll, stake in bankroll units, a "capped at 25%" note when the cap binds, "No bet" at zero | `kelly.kelly_fraction` with its `max_fraction = 0.25` cap unchanged |
| PrizePicks entry EV | entry type (Power, Flex), 2 to 6 per-leg hit probabilities | P(each hit count), expected payout multiple, EV per unit as a percent | **new** `app/core/prizepicks_entry.py` (no entry math exists in core today; `prop_ev.py` holds per-leg decimals only) |

Also in scope:

- The shared fixture, a Python test and a Vitest test that both read it.
- A **Tools** link in the top bar and phone drawer through `EXTRA_LINKS` in
  `web/src/utils/sportNav.ts`, placed before How it works, and the
  `Tools · Lineform` document title.
- Input parsing and validation shared by the five cards (empty, out of range,
  not a number), each card showing the shared empty placeholder (as `fmtPct`
  does for a null) and one short reason until its
  input is valid.

## Out of scope

- Any endpoint, router, schema, repository or migration. The page makes no
  network request.
- Parlay payout across sportsbook prices, devig methods other than
  multiplicative normalization (power, Shin, additive), three-way markets,
  alternate-line ladders, `near_even_rungs`.
- Goblin and demon adjusted PrizePicks entry payouts, promos, insured or
  "rebooted" entries. The entry calculator uses one standard payout table.
- Feeding a slate row or a board line into a calculator ("Open in calculator"),
  URL-persisted inputs, saved bankrolls. Possible later items.
- Any change to the existing `web/src/utils/odds.ts` helpers or their callers
  (`devigP1` returns `null` on a zero total where Python returns 0.5/0.5; that
  stays, the new port follows Python).
- Coloring outputs green or red. See Notes.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared fixture and the Python side of it** - create
  `api/tests/fixtures/calculator_cases.json` with input/expected pairs for
  every function in the table except the PrizePicks entry (that is Step 3),
  expected values produced by the current `app/core/` functions (generate them
  once in a scratch script outside `api/`, then paste; no generator in the
  repo). Add `api/tests/test_calculator_cases.py` that loads the file and
  asserts each core function returns the stored value (`pytest.approx`,
  `abs=1e-9` for floats, exact for ints). Required cases: `-110/-110`,
  `-150/+130`, `+100`, `-100`, a `prob_to_american` at 0.5, clamped extremes
  (0 and 1 probability), `decimal_to_american(2.125)` (Python rounds 112.5 to
  112, half to even), `decimal_to_american(1.0)` (`-10000`), a Kelly case where
  the 25% cap binds at multiplier 1, a negative-edge Kelly case (0), and EV at
  break-even (0). *Done when:* `pytest tests/test_calculator_cases.py` passes
  and an edit to any expected value makes it fail.
- [x] **Step 2 - TypeScript port of odds, no-vig, EV and Kelly** - add
  `web/src/utils/oddsMath.ts` with `americanToDecimal`, `decimalToAmerican`,
  `probToAmerican`, `decimalToProb`, `devigTwoWay`, `overround`,
  `expectedValue`, `kellyFraction` and a `roundHalfEven` helper (Python's
  `round`; `Math.round` gives 113 on the 112.5 case). Reuse `americanToProb`
  from `~/utils/odds`. `web/src/utils/oddsMath.test.ts` imports the same JSON
  and asserts every case (`toBeCloseTo(x, 9)` for floats, `toBe` for ints).
  *Done when:* `npm run test` passes both suites, `npm run build` typechecks
  the cross-tree JSON import, and the 2.125 case returns 112 in TS.
- [x] **Step 3 - PrizePicks entry module (Python)** (payout table confirmed by the user 2026-11-11) - add
  `api/app/core/prizepicks_entry.py`: a named payout table
  `POWER_PAYOUTS[n]` and `FLEX_PAYOUTS[n][hits]` for 2 to 6 legs with a
  `PAYOUTS_CHECKED` date comment, `hit_count_distribution(probs)` (exact
  Poisson-binomial by dynamic programming over legs, not an i.i.d. binomial,
  since legs differ) and `entry_ev(probs, kind)` returning the distribution,
  the expected payout multiple and EV = expected multiple - 1. Reject fewer
  than 2 or more than 6 legs, an unknown kind, flex at 2 legs, and a
  probability outside [0, 1] with `ValueError`. Add entry cases to the fixture
  (equal legs 0.5 and 0.6 at several sizes, mixed legs, a leg at 1.0, a leg at
  0) and to `test_calculator_cases.py`, plus a test that each distribution sums
  to 1. *Done when:* the pytest file passes, and the payout table has been
  confirmed by the user against the PrizePicks app (see Notes) before the
  numbers are committed.
- [x] **Step 4 - PrizePicks entry module (TypeScript)** - port it as
  `web/src/utils/prizepicksEntry.ts` with the same table and errors (returned
  as a typed result, not thrown, so the card can render the reason), asserted
  against the fixture's entry cases in `prizepicksEntry.test.ts`. *Done when:*
  both suites pass on the same entry cases.
- [x] **Step 5 - Input parsing** - `web/src/utils/calculatorInputs.ts`:
  `parseAmerican` (integer, `|x| >= 100`, accepts a leading `+`),
  `parseDecimal` (`> 1`), `parsePercent` (0 to 100 exclusive, returns 0-1),
  `parsePositive` (bankroll, stake), each returning
  `{ ok: true, value } | { ok: false, reason }`; an empty string is its own
  quiet state, not an error. Tested in `calculatorInputs.test.ts`. *Done when:*
  tests cover `+150`, `-110`, `99`, `-99`, `1.0`, `abc`, `""`, `0`, `100`.
- [x] **Step 6 - Page with the converter, no-vig and EV cards** -
  `web/src/pages/ToolsPage.tsx` (lazy route `/tools` in `App.tsx`) and
  `web/src/pages/tools.css`, compact page head (title "Tools", one status line:
  "Runs in your browser. Nothing is saved or sent."), a responsive card grid,
  Ant Design `Input` / `Segmented`; outputs use tabular numbers and theme
  variables only. *Done when:* `/tools` renders the three cards; `-110/-110`
  shows 50.0% / 50.0%, fair `-100` / `-100` (Python's `prob_to_american`
  returns -100 at exactly 0.5, and the page keeps it), overround 4.8%; EV at
  55% and `-110` shows +5.0% and break-even 52.4%; invalid input shows the
  empty placeholder and a reason; no console errors.
- [x] **Step 7 - Kelly and PrizePicks cards** - the two remaining cards on the
  same page; the PrizePicks card adds and removes leg inputs (2 to 6, flex
  disabled at 2) and lists the hit-count distribution with each payout.
  *Done when:* Quarter Kelly at 55% and `-110` reads 1.38% of bankroll and
  the stake for a 1000 bankroll reads 13.75; a 6-leg flex with every leg at 60%
  matches the fixture's EV; the cap note appears on a capped case.
- [x] **Step 8 - Nav entry and title** - add `{ key: '/tools', label: 'Tools' }`
  to `EXTRA_LINKS` before How it works; update `sportNav.test.ts` expectations
  (top-bar links, phone menu, `documentTitle('/tools')`). *Done when:* the top
  bar and phone drawer show Tools, it is active on `/tools` only, the tab title
  reads `Tools · Lineform`, and the Verify command passes.
- [x] **Step 9 - Browser check** - run the app, check each card's done-when at
  1280px and 375px (no horizontal scroll, cards stack), screenshot both.
  *Done when:* screenshots attached to the review packet.

## Files / areas

- New: `api/tests/fixtures/calculator_cases.json`, `api/tests/test_calculator_cases.py`,
  `api/app/core/prizepicks_entry.py`
- New: `web/src/utils/oddsMath.ts` (+ test), `web/src/utils/prizepicksEntry.ts`
  (+ test), `web/src/utils/calculatorInputs.ts` (+ test),
  `web/src/pages/ToolsPage.tsx`, `web/src/pages/tools.css`
- Added in Step 6: `web/src/utils/calculators.ts` (+ test) turns field text
  into each card's display values so that logic is tested, and the cards live
  in `web/src/components/tools/` per the frontend layout rule. The app uses
  `HashRouter`, so the page is at `/#/tools`.
- Changed: `web/src/App.tsx` (route), `web/src/utils/sportNav.ts` and
  `sportNav.test.ts` (link, title)
- Read only: `api/app/core/odds.py`, `kelly.py`, `prop_ev.py`, `web/src/utils/odds.ts`

## Data / contracts

- **Fixture shape (load-bearing, both suites read it):**

  ```json
  {
    "american_to_decimal": [{ "in": [-110], "out": 1.9090909090909092 }],
    "kelly_fraction": [{ "in": { "prob": 0.55, "odds_american": -110, "multiplier": 0.25 }, "out": 0.01375 }],
    "entry_ev": [{ "in": { "probs": [0.6, 0.6, 0.6], "kind": "flex" }, "out": { "distribution": [0.064, 0.288, 0.432, 0.216], "expected_multiple": 1.08, "ev": 0.08 } }]
  }
  ```

  One key per function, Python names; each case is `in` (positional list or
  keyword object) and `out`. Values above are illustrative; Step 1 and Step 3
  write the real ones from Python.
- `EntryKind = 'power' | 'flex'`; `EntryResult = { distribution: number[]
  (index = hits), expectedMultiple: number, ev: number }`.
- No API shape, stored field or route payload changes.

## Testing

Test gate is on. Logic steps ship tests in the same diff:

| Step | Test |
|---|---|
| 1 | `api/tests/test_calculator_cases.py` (core odds, devig, EV, Kelly against the fixture) |
| 2 | `web/src/utils/oddsMath.test.ts` (same fixture) |
| 3 | `test_calculator_cases.py` entry cases plus distribution sums to 1 |
| 4 | `web/src/utils/prizepicksEntry.test.ts` (same entry cases) |
| 5 | `web/src/utils/calculatorInputs.test.ts` |
| 8 | `web/src/utils/sportNav.test.ts` updated |

Steps 6, 7 and 9 are UI and ride on the browser check and build. Final gate:
`npm --prefix web run verify && cd api && python -m pytest` with the API venv.

## Notes for the AI

- **Formulas are identical, not similar.** Port the Python line for line,
  including its clamps (`prob_to_american` clamps to `[1e-6, 0.999999]`),
  its zero-total fallback (`devig_two_way` returns 0.5/0.5), the
  `decimal_to_american` `-10000` floor, and Python's half-to-even rounding.
  If a port needs a different branch, the fixture should prove it.
- **The PrizePicks payout table is unverified.** No entry table exists in the
  repo and PrizePicks changes it. Candidate standard figures to confirm with
  the user before Step 3 commits them: Power 2: 3x, 3: 6x, 4: 10x, 5: 20x,
  6: 37.5x; Flex 3: 3x / 1x (3 / 2 hits), 4: 6x / 1.5x, 5: 10x / 2x / 0.4x,
  6: 25x / 2x / 0.4x. Show the table on the card with "Standard payouts as of
  <date>; check the app" so a stale figure is visible.
- **No green or red.** These are user-entered numbers, not model signals, but
  the project keeps edge colors gray until a rule adopts them; show the sign
  (`+5.0%`, `-2.3%`) in the default text color.
- `app/core/prizepicks_entry.py` stays pure (no I/O). Nothing in the API
  imports it yet; it exists so the fixture has a Python source of truth and a
  later board feature can reuse it.
- The web test imports the fixture by a relative path out of `web/`
  (`../../../api/tests/fixtures/calculator_cases.json`); `resolveJsonModule`
  is on. If `tsc -b` rejects the out-of-`include` file, fall back to a Vitest
  `fs.readFileSync` with a typed parse, not to a second copy of the fixture.
- Page head per the house style: title plus one status line, no eyebrow or
  filler subtitle. Theme variables from `src/index.css`, dark mode only, no em
  dashes in copy.
- Parallel worktrees (record-strip, projection-history, board-filters,
  prop-reasons) also edit `build-plan.md` and possibly `sportNav.ts` or
  `App.tsx`; expect small merge conflicts there at `/complete`.
- The project overview was not regenerated for this incremental item; do it
  at `/complete` or the next `/overview` run.
- Update `docs/SportApp-Employer-Interview-Guide.md` at `/complete` if it
  exists on this machine (shared fixture keeps web and API math in lockstep).
