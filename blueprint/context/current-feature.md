# Feature: Retire tennis tiers

**From build-plan:** feature 48f
**Status:** not started (spec awaiting owner review)

## Goal

Tennis PrizePicks prop lines stop carrying LOCK, STRONG, LEAN or PASS. The prop
board, the match page and best picks show each line's projection, gap (projection
minus line) and P(over) against its payout's break-even (standard, goblin,
demon), gray and unranked, the way NFL and NBA lines read before any slice is
adopted. This has to land before 48e writes its pre-registered rule, so that
rule grades P(over) slices instead of tiers (owner decision 2026-10-28).

## In scope

- **API tennis prop lines** (`app/routers/props.py` `_enrich`): `confidence` is
  always null. The tier ceiling, the cap and downgrade helpers and the
  `no_market_total` PASS cap go away. Hard-block flags still null
  `recommendation`. `p_over`, `p_under`, `p_push`, `hit_probability`,
  `break_even_pct`, `ev_pct`, `stat_avg` and every data-quality flag stay as
  they are. `no_market_total` stays a flag.
- **`GET /tennis/props/top`**, the only route that ranks by tier. With no
  tiers it can only ever return nothing. Remove it, along with the unused web
  `fetchTopProps` (see question 3).
- **Snapshots** keep recording `p_over`, `p_under`, `hit_probability`,
  `recommendation`, `break_even_pct` and `ev_pct` under `props-v3`, with
  `confidence` written as null. No migration (the column is already nullable).
- **The 32b tier record becomes history:** `TIER_RULE_VERSION` goes back to
  `props-v2`, so the model page's tier cards and `/tennis/model/prop-tiers`
  show the frozen v2 record, labelled retired. The re-registration of the v3
  tier rule (48a) is withdrawn before any v3 row has been graded by it.
- **Best picks:** `generate_prop_picks` stops turning PrizePicks lines into
  picks, so no prop line is ranked or counted as a best pick or an angle. The
  lines still show as gray rows on the match page and the board (question 2).
  Market-priced picks (moneyline reference, Total Games, Game Spread, derived,
  serve-edge) keep their current behaviour.
- **Web tennis prop utils** (`tennisPropBoard.ts`, `tennisPropCards.ts`,
  `tennisMatch.ts`, `unifiedTennis.ts`): no tier rank, no "Ready"/"Lean"
  trust, no EV-based ordering or EV tone for PrizePicks lines, no OVER/UNDER
  pick label. Lines sort by start time, then player, then stat. Prop-health
  "scored" counts lines with a P(over), not a tier.
- **Web components:** `TennisPropTable` (the tier column becomes P(over) vs
  break-even), `TennisMatchDetail` (prop rows show projection, gap, P(over)
  and break-even, with no tier tag, and the top-EV prop no longer leads),
  `TennisIntelligencePage` (the LOCK and STRONG counts go),
  `TennisModelPage`/`ModelTierCards` copy (props-v2 history, retired) and
  `howItWorksContent.ts`.
- **The shared prop code the build plan names:** `app/core/prop_ev.py`'s
  `assess_prop` stays, because market picks in `best_picks.py` and the
  bankroll builder still read `assessment.confidence` from
  `ev_confidence_tier`. The PrizePicks path just stops reading it, and the
  module docstring says so. The dead web tier helpers go: `generateOpinion`
  (`web/src/utils/props.ts`, no importers) and `confidenceColor`
  (`web/src/utils/odds.ts`, no callers). See question 1 on the NBA side.
- **Ask Lineform:** the prompt line "give its tier" stays for priced market
  picks. Tennis prop rows leave `get_top_props` with best picks, and an eval
  case that expects one is updated.

## Out of scope

- **48c** (match simulation, specced in a parallel session), 48d, 48e and 48g.
  This feature registers no rule and adopts nothing.
- Any change to projection, probability, push or EV math. That would need a
  new projection version, and none is cut here.
- Tiers on match-market picks: moneyline reference, book-priced Total Games and
  Game Spread, derived and serve-edge picks (`confidence_tier` in
  `app/core/poisson.py`, `bettable_criteria.py`). That includes the Win a Set
  rows on the prop board, which come from the derived pick (question 4).
- The retired bankroll builder and the Parlays page.
- NFL and NBA prop pipelines. Nothing there reads a tennis tier.
- Deleting or re-grading any `props-v2` or `props-v3` snapshot.
- Regenerating `project-overview.md`. `/complete` records the change, and a
  later `/overview` refresh picks it up.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Tennis prop lines carry no tier (API)** - in `_enrich`, stop
  assigning `confidence` and delete `_CONF_RANK`, `_MAX_PROP_CONFIDENCE`,
  `_cap_confidence`, `_downgrade_confidence` and the PASS cap. Hard blocks still
  null `recommendation`. Remove `/props/top`, its `_CONF_*`/`_MIN_CONF_MAP` and
  `_prop_score`. Update `test_props_v3_caps.py` and the props router tests.
  *Done when:* a pytest builds lines for a complete standard prop, a
  `no_market_total` prop, an `ungraded_stat` first-set prop and a hard-blocked
  prop, and asserts `confidence is None` on all four, unchanged `p_over`,
  `hit_probability` and `break_even_pct` on the first three (compared against
  values pinned from `master` before the change), the `no_market_total` flag
  still present, and `recommendation is None` only on the hard-blocked one.
  `/tennis/props/top` returns 404. *Added at build time (from Step 3):*
  `generate_prop_picks` and the `prop_lines` path through `build_best_picks`
  and `best_picks_response` are removed, so no PrizePicks line becomes a best
  pick, and best picks no longer builds board rows.
- [ ] **Step 2 - Snapshots and the tier record** - snapshots write
  `confidence=None` under `props-v3`, and the `PROJECTION_VERSION` comment is
  reworded (bump on projection, probability or EV changes). `TIER_RULE_VERSION`
  becomes `props-v2`, and the 48a note on the v3 re-registration is withdrawn
  in `app/core/track_record.py`. The `tennis_prop_snapshots` backtest's tier
  section prints "no tiers under props-v3" for a v3 run, and v2 still reads
  with `--version props-v2`. *Done when:* a pytest snapshots an enriched line
  and asserts `confidence is None` with `p_over` and `recommendation` kept, and
  `build_tier_grading` reports `projection_version == "props-v2"`. The report
  test covers the v3 no-tier message.
- [ ] **Step 3 - Ask check** - the best-picks half of this step moved into
  Step 1, because nulling `confidence` made `generate_prop_picks` skip every
  line and broke its tests. Check `ask_results`/Ask tools and
  `ask_questions.json` for tennis prop pick assumptions and update them.
  *Done when:* the Ask results tests pass, and `python -m app.evals.ask --dry-run`
  loads without a case that expects a tennis prop pick.
- [ ] **Step 4 - Shared tier helpers** - delete the dead `generateOpinion`
  (and `web/src/utils/props.ts` with it, since that is its only export, once
  you approve deleting the file) and `confidenceColor`. Reword the
  `prop_ev.py` docstring: its tier now grades only market picks, never a
  PrizePicks line. Question 1 decides whether this step also touches NBA.
  *Done when:* `grep -rn "LOCK\|STRONG" api/app/routers/props.py web/src/utils/odds.ts`
  finds nothing, `web/src/utils/props.ts` is gone or holds no tier, and pytest
  plus `npm --prefix web run build` pass.
- [ ] **Step 5 - Web prop utils, gray and unranked** - in `tennisPropBoard.ts`,
  `isTennisRateable` stops requiring `evPct > 0`, `trustLabel` returns
  `Reference` or `Review`, and `compareLines` orders PrizePicks lines by start
  time, player and stat with no tier or EV. Win a Set keeps its own ordering.
  `tennisPropCards.ts` adds `gapText` (signed projection minus line),
  `pOverPct`, the break-even for the line's payout, and `pickLabel` with no
  OVER/UNDER (goblin and demon read "Over only"). The card drops `confidence`,
  and `evTone` is null for PrizePicks. `tennisMatch.ts` `propRank` loses the
  tier. `unifiedTennis.ts`: PrizePicks props never count as priced or ranked,
  and `assessPropsHealth.scored` counts `pOver != null`. Update the matching
  `*.test.ts`. *Done when:* `npm --prefix web run test` passes with new cases:
  two lines with different EVs keep start-time order; a goblin card reads
  "Over only" with a 75.8% break-even (1 / `GOBLIN_LEG_DECIMAL` 1.32) beside
  its P(over); the gap reads "+1.4" for projection 6.9 on a 5.5 line;
  a card built from a LEAN-confidence fixture exposes no tier.
- [ ] **Step 6 - Web components and copy** - `TennisPropTable` swaps its tier
  column for P(over) vs break-even and shows the gap. `TennisMatchDetail`
  prop rows show projection, gap, P(over) and break-even with no
  `ConfidenceTag`, and props keep board order instead of top EV leading.
  `TennisIntelligencePage` drops the LOCK and STRONG counts. The model page
  heading and `ModelTierCards` note say the tier record is `props-v2` history,
  retired 2026-10-28, and that tennis lines are now rated by P(over) against
  break-even pending 48e. `howItWorksContent.ts` gets the same line. *Done
  when:* `npm --prefix web run build` passes; the board, a match page and the
  model page are screenshotted against the local API with no
  LOCK/STRONG/LEAN/PASS text on any PrizePicks row; and every PrizePicks row
  shows a gray projection, gap and P(over) vs break-even.
- [ ] **Step 7 - Verify and docs** - run the full Verify command. Update
  `docs/SportApp-Employer-Interview-Guide.md` if it exists locally (it is
  untracked and never staged): tennis props are now rated like NFL and NBA,
  with no tiers. *Done when:* `npm --prefix web run verify && cd api && python -m pytest`
  passes, and the guide edit is noted or reported as skipped.

## Files / areas

- API: `app/routers/props.py`, `app/core/prop_ev.py`,
  `app/services/tennis/prop_snapshots.py`, `app/core/track_record.py`,
  `app/backtest/tennis_prop_snapshots.py`, `app/services/tennis/best_picks.py`,
  `app/schemas/tennis.py` (comment on `confidence`), and `app/core/ask_results.py`
  and `app/evals/ask_questions.json` only if Step 3 finds a prop-pick assumption.
- API tests: `test_props_v3_caps.py`, `test_props_router_*.py`,
  `test_props_audit_projection.py`, `test_prop_ev.py`, `test_prop_snapshots.py`,
  `test_prop_snapshot_report.py`, `test_track_record_*.py`, `test_best_picks*.py`,
  `test_tennis_best_picks_response.py`, `test_ask_results.py`.
- Web: `utils/tennisPropBoard.ts`, `utils/tennisPropCards.ts`,
  `utils/tennisMatch.ts`, `utils/unifiedTennis.ts`, `utils/props.ts`,
  `utils/odds.ts`, `api/tennis.ts`, `components/tennis/TennisPropTable.tsx`,
  `components/tennis/TennisMatchDetail.tsx`,
  `components/tennis/model/ModelTierCards.tsx`, `pages/TennisIntelligencePage.tsx`,
  `pages/TennisModelPage.tsx`, `pages/howItWorksContent.ts`, plus their tests.

## Data / contracts

- **Load-bearing for 48e and 48g:** a tennis `PropLine` always has
  `confidence: null`. The field stays in the schema (shared `PropLine` type,
  older clients), but it is never set. P(over) is `p_over`, and the payout's
  break-even is `break_even_pct` (standard, goblin or demon by `odds_type`).
  48e grades `p_over`/`p_under` against `BREAK_EVEN_BY_ODDS_TYPE` per slice and
  never reads `confidence`.
- **Load-bearing:** `props-v3` snapshots from before this feature hold a LEAN
  or PASS `confidence`, and later ones hold null. Their P(over) is the same
  code either way, so 48e treats `props-v3` as one sample and ignores
  `confidence`. No version bump, because projection and probability are
  unchanged (question 5).
- **`TIER_RULE_VERSION = "props-v2"`:** the tier record reads only v2 from now
  on, and no tier rule exists for v3 or later.
- `BestPickSchema.confidence` stays a required string. PrizePicks lines simply
  never become best picks, so market picks keep their tiers unchanged.
- `/tennis/props/top` is removed (no web or Ask caller).
- No migration.

## Testing

Test gate on. Logic-bearing steps ship tests:

- Step 1: the `_enrich` assertions above (confidence null, probabilities
  unchanged, flags kept).
- Step 2: snapshot builder and tier-grading version, plus the report message.
- Step 3: best picks with PrizePicks lines yield market picks only.
- Step 4: deletion only. The existing `test_prop_ev.py` must still pass
  unchanged, which proves market-pick tiers did not move.
- Step 5: Vitest for ordering, gap, P(over) vs break-even, "Over only" and
  prop-health counts, with fixed timestamps (`format.test.ts` style).
- Step 6: components are not unit-tested. Build, plus screenshots of the
  board, a match page and the model page against the local API.
- Step 7: the full Verify command.

## Notes for the AI

- Read `docs/commands.md` before running any ingest. This feature needs none.
  Snapshot tests use fixtures, not the database.
- Keep `core/` pure. Routers stay thin; the PrizePicks enrichment already lives
  in the router, and this feature does not move it.
- Gray means `is-neutral` styling with no green or red on PrizePicks rows. The
  `invariants-review` gray-signal rule applies, so run `/invariants-review`
  before `/complete`.
- Pin before/after probabilities in the Step 1 test, so it proves no math
  moved.
- **Coordination with 48c** (spec on `feature/48c-match-simulation`, checked
  2026-10-29): 48c steps 1-5 are new pure modules and run in parallel. Its
  steps 6-8 wait for 48f on `master`, then edit only `_enrich`'s projection
  block and `enrich_with`. To keep the two apart:
  - Do not touch `prop_probs.py`, the projection inputs, `tennis_first_set.py`,
    `enrich_with` or `_enrich_with_total`.
  - Leave the hard-block flag list (including `bo5_unsupported_stat`) as it is.
  - Keep `PropLine.confidence` in the schema.
  - 48c takes the next unused `PROJECTION_VERSION` after this feature:
    `props-v4` if 48f keeps v3 (question 5), `props-v5` if it bumps.
  - 48c's seed note says best-pick cards read the simulation's values. After
    48f's Step 3 no PrizePicks line is a best pick, so that point no longer
    applies (harmless).
  - Both branches edit `current-feature.md`. When 48c merges `master` after
    48f's `/complete`, keep 48c's spec over the reset stub.
- No em dashes in new comments, copy or docs.

## Open questions for review

1. **"Coordinated with the NBA LOCK removal":** `master` has no NBA tier. The
   NBA board, `nbaProps.ts` and the NBA API carry no `confidence`, and the only
   LOCK/STRONG code is tennis (plus Parlays and the bankroll builder). This
   spec reads "shared prop code" as `prop_ev.py`'s tier helpers and the dead
   web `props.ts`/`odds.ts` helpers, and touches no NBA file. Is there NBA work
   in flight (another branch or session) that this should line up with?
2. **Best picks:** this spec removes PrizePicks lines from best picks entirely,
   and they show only as gray rows on the board and the match page. The
   alternative keeps them in best picks as gray reference items, which would
   need `BestPickSchema.confidence` to become optional and touches Ask. Removal
   is simpler and matches "unranked". OK?
3. **`/tennis/props/top`:** remove it (this spec), or keep it ranking by
   P(over) margin? The second option would be ranking before 48g.
4. **Win a Set rows on the prop board** still show LOCK/STRONG from the
   derived match pick (`winASetStrength`). This spec leaves them alone, as
   match-model angles outside "tennis props". Should they turn gray too?
5. **Version:** keep `props-v3` (P(over) unchanged, and accrued v3 snapshots
   stay usable for 48e), or bump to `props-v4` so the pre- and post-48f rows
   never pool?
