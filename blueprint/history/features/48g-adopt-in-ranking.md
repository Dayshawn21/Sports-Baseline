# Feature: Adopt in ranking

**From build-plan:** feature 48g (parent 48, tennis prop rebuild)
**Status:** complete (2026-10-29)

## Goal

Tennis PrizePicks lines become picks only where 48e's pre-registered rule
(`tennis-props-check-v1`) has adopted their slice. A live line is keyed with
48e's own `slice_key` and exclusions. If its slice reads adopt, it is ranked
by P(side) minus break-even, labelled with its side, and shown in the
validated signal color. Every other line stays gray and unranked, as since
48f.

Today no slice is adopted, because the grader has never run on real data. So
the shipped result has to be correct with an **empty adopted set**: the board
looks exactly as it does on `master`. Tennis is the first sport to wire
adoption into ranking. NFL's 27h and NBA's 44c are unbuilt, so there is no
existing adoption code to copy. The precedent is the rule shape, not the code.

## Which projection version's verdicts are served

**48g serves verdicts only for the version the board displays:
`PROJECTION_VERSION` in `app/services/tennis/prop_snapshots.py`, which is
`props-v3` today.** A board line's P(over) is a v3 number, so only a v3
verdict can rank it.

- 48c's `props-v4` runs in shadow (its spec: "the props page and best picks
  keep showing `props-v3`"). Its verdicts can be graded with the CLI below
  (`--version props-v4`), but they are never served while v4 is shadow. The
  read path drops any stored verdict whose version is not `PROJECTION_VERSION`.
- If a later item makes v4 the board's version, verdicts follow it with no
  48g change. The v3 verdicts stop being served the moment the board stops
  showing v3 numbers, and the v4 snapshot must be written before any v4 line
  can rank.
- 48g imports `PROJECTION_VERSION` and never edits that file (48c owns it).

## How the adopted set reaches the request path

Grading means reading every frozen snapshot plus the box-score joins. That
is too heavy for Render's 512 MB, so the grade never runs on a request
(AGENTS.md memory rule):

1. A new CLI, `python -m app.ingest.tennis_prop_adoption [--version props-v3]
   [--as-of YYYY-MM-DD] [--dry-run]`, runs 48e's `check` the same way the 48e
   grader does. It stores a small payload in `report_snapshots`: the rule, the
   version, `as_of`, the counts, and the **adopted slice keys only**.
2. `GET /tennis/props/prizepicks` reads that row (one small JSONB value),
   decodes it into a `frozenset[TennisSlice]`, and applies it to the lines it
   already built.
3. **A missing, malformed, wrong-rule or wrong-version row means an empty
   set.** The board stays fully gray and is still served. This deliberately
   differs from NFL's 503 for a missing snapshot: adoption only adds signal,
   so its safe default is "nothing adopted", not "no page". The case is
   logged at warning level.
4. **Staleness does not matter for correctness.** Once a verdict sample is
   filled it is fixed (27i's `verdict_sample`), and a reject is final. So an
   old row can only lag behind a newer adopt. It can never keep serving a
   slice that has since been rejected. The payload's `asOf` is shown, so the
   lag is visible.

## In scope

- **Pure live adoption** (`app/core/tennis_prop_adoption.py`). It builds a
  `TennisFrozenLine` from each live line with an `unsettled` outcome, so
  `slice_key` is 48e's own function and nothing is re-derived. It applies
  48e's exclusions in 48e's order: `EXCLUDED_FLAGS`, `UNKNOWN_ODDS_TYPE` and
  `NO_PROBABILITY` (push-excluded P(over) and P(under)). It takes the side
  from 27i's `pick_side` with `MIN_PICK_MARGIN`, and collapses ladders with
  `one_pick_per_bet` before slicing (the grader's order). It returns the
  surviving picks whose slice is in the adopted set. Lines already started
  (`start_time <= now`) are never picked, because the rule graded pre-start
  snapshots only.
- **Payload codec** in the same core module: encode a `CheckResult` into the
  stored payload, and decode a payload back to a `frozenset[TennisSlice]`,
  rejecting a wrong rule, wrong version or malformed shape.
- **Writer CLI** `app/ingest/tennis_prop_adoption.py` with `--dry-run`. It
  reuses the grader's loading (`get_prop_check_snapshots`,
  `get_box_score_candidates`, `to_frozen_lines`) and stores through
  `report_snapshots.upsert_snapshot`.
- **Live tours on `Prop`**: `get_today_props` also selects the resolved
  match's `tour` and both players' tours (`match_tour`, `p1_tour`,
  `p2_tour`), joined on the same `COALESCE(relinked.id, p.match_id)` the row
  already reports. This gives `display_tour` the same inputs 48e's
  repository read uses. These are new defaulted fields on the `Prop`
  dataclass.
- **Serving**: a thin `app/services/tennis/prop_adoption.py`
  (`load_adopted(db)` and `apply_adoption(props, lines, adopted, now)`), called
  by `get_prizepicks_props` only, after `_enrich_props`. A new
  `adopted_pick: AdoptedPick | None` field on `PropLine`, null unless adopted.
- **Web board** (`tennisPropBoard.ts`, `tennisPropCards.ts`,
  `TennisPropTable`): adopted lines lead the rateable bucket, ordered by
  margin, then the rest in 48f's start-time order. An adopted line shows its
  side (`OVER` / `UNDER`) and margin in `--positive`. An adopted goblin line
  joins the rateable bucket (today every goblin is in "other"). Everything
  else is unchanged and gray.
- **Web match page and Intelligence page**: adopted prop rows lead and use
  the signal color. Both read the same `compareLines`, so the ordering is
  shared.
- **Workflow** `tennis-prop-adoption.yml`, `workflow_dispatch` only (see
  question 2), running the writer CLI.
- **Docs**: one line in `AGENTS.md` (Ingest commands) and a section in
  `docs/commands.md`. The `howItWorksContent.ts` line from 48f becomes
  "ranked only where the forward check adopts a slice".

## Out of scope

- **48c's files** (`app/core/tennis_match_sim.py`, `tennis_match_chain.py`,
  `app/backtest/tennis_match_sim.py`, `app/ingest/prop_snapshots.py`,
  `app/services/tennis/prop_snapshots.py` and their tests). The last one is
  imported for `PROJECTION_VERSION` only. 48g writes nothing to
  `prop_projection_snapshots`, and `enrich_with`'s signature is unchanged, so
  48c's snapshot path is untouched.
- **Any change to 48e's rule module** `app/core/tennis_prop_check.py`, or to
  `prop_ranking_rule.py` / `prop_ranking_check.py`. 48g only imports them.
- **Best picks, angles, Ask Lineform and the bankroll builder.** 48f removed
  PrizePicks lines from best picks, and putting adopted lines back there is a
  later call (question 1).
- **Showing 48e verdicts on `/tennis/model`** (a later item). The payload
  carries only what serving needs.
- **The first real grade.** Running the writer without `--dry-run`, or even
  with it, against the real database reads v3 outcomes. That is the owner's
  separate yes in chat, after merge, as for the 48e grader.
- **NFL 27h and NBA 44c.** The core module is tennis-only, so no shared code
  is invented for sports with no adopted slice.
- The DraftKings source (`/tennis/props/dk`), moneyline rows and Win a Set
  rows. These are not 48e slices and keep their current behaviour.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure live adoption** - `app/core/tennis_prop_adoption.py`:
  `live_line(...) -> TennisFrozenLine` (outcome `UNSETTLED = "unsettled"`)
  and `adopted_picks(lines, adopted, now) -> dict[int, Pick]` as described in
  In scope. When `adopted` is empty it returns `{}` before doing any work.
  The `FrozenCall` it builds for `one_pick_per_bet` carries a placeholder
  outcome that ranking never reads (`Pick.hit` is unused), and a comment says
  so. Tests in `api/tests/test_tennis_prop_adoption.py`, synthetic only:
  - **Parity with 48e.** For lines that cover every exclusion and both
    anchors (16.5, 17.0, None), a settled copy sent through 48e's
    `to_frozen_call` gives the same exclusion or the same push-excluded
    probabilities, and `slice_key` gives the same key.
  - An empty adopted set gives `{}`.
  - An adopted slice picks a line. The same line with an excluded flag, an
    unknown odds type, `p_push` of 1, or a margin under 0.03 does not.
  - A goblin under is never a pick.
  - A three-rung goblin ladder yields one pick (the best-margin rung), and
    none at all when that rung's slice is not adopted but a weaker rung's is.
    This matches the grader, which slices by the surviving rung.
  - A WTA 125 line (`CHALLENGER` match with WTA players) keys as `WTA 125`.
  - A line starting at `now` is not picked; one starting a minute later is.
  - A line with no `player_id`, `match_id` or `start_time` is not picked.

  *Done when:* those tests pass, the module imports nothing from `app.db`,
  `app.repositories` or `app.services`, and
  `git diff master -- api/app/core/tennis_prop_check.py api/app/core/prop_ranking_rule.py`
  is empty.
  *Build-time change:* there is no `live_line` helper and no copied
  exclusion code. `_live_call` sends the live line through 48e's own
  `to_frozen_call` with a placeholder outcome and its own week marked
  finished, so the flags, odds type and push-excluded probabilities are
  48e's code, not a copy. The service (Step 5) builds the `TennisFrozenLine`
  with `outcome=UNSETTLED`. The test for a missing `player_id`, `match_id` or
  `start_time` moves to Step 5, because those lines never become a
  `TennisFrozenLine`.
- [x] **Step 2 - Payload codec** - in the same module:
  `to_payload(result, version, as_of, computed_at) -> JsonObject` and
  `adopted_from_payload(payload, version) -> frozenset[TennisSlice] | None`
  (None means unusable, with the reason logged by the caller). Also
  `adoption_report(version) -> "tennis_prop_adoption:<version>"` and
  `ADOPTION_SEASON = 0`. *Done when:* tests show a round trip of a
  `CheckResult` with two adopted, one rejected and one insufficient slice that
  decodes to exactly the two adopted keys. The payload holds no hit rate,
  `n` or SE for any slice (it keeps only adopted keys and counts). A wrong
  `rule`, a wrong `projectionVersion`, a missing `adopted` list and a slice
  with an unknown anchor or side each decode to None. An empty `adopted`
  list decodes to an empty frozenset, not None.
- [x] **Step 3 - Writer CLI** - `app/ingest/tennis_prop_adoption.py`. It
  loads exactly as `app.backtest.tennis_prop_check._main` does, runs
  `check`, then prints a one-screen summary (rule, version, as-of, decided
  and adopted counts, and the adopted keys). Without `--dry-run` it upserts
  the payload under `adoption_report(version)` / `ADOPTION_SEASON`, so a v4
  grade never overwrites the v3 row. A pure `summary(...)` is tested on a synthetic
  result. *Done when:* the summary test passes and
  `python -m app.ingest.tennis_prop_adoption --help` runs. **No run against
  a database** in this step or any later one.
- [x] **Step 4 - Live tours on `Prop`** - `get_today_props` selects
  `COALESCE(relinked.tour, m.tour) AS match_tour` plus `p1_tour` and
  `p2_tour` from the resolved match's two players, and `Prop` gains three
  defaulted `str | None` fields. *Done when:* a repository test in the style
  of the existing props repository tests asserts that the SQL joins the
  players on the resolved match id and maps the three columns, and the
  existing props and snapshot tests pass unchanged.
  *Build-time change:* `CASE WHEN relinked.id IS NOT NULL THEN ... ELSE ...`
  instead of `COALESCE`, for the tour and both player joins, as
  `match_start_time` does, so a relinked match never borrows the stale
  link's tours.
- [x] **Step 5 - Serve on the PrizePicks route** -
  `app/services/tennis/prop_adoption.py`:
  - `load_adopted(db)` reads the row for `PROJECTION_VERSION` through
    `report_snapshots.get_snapshot`, decodes it, and returns an empty set
    (logging why) on a miss.
  - `apply_adoption(props, lines, adopted, now)` builds live lines from each
    `(Prop, PropLine)` pair, calls `adopted_picks`, and sets
    `adopted_pick = AdoptedPick(side, probability, break_even, margin,
    rule, projection_version)` on the picked lines.

  `get_prizepicks_props` calls both after `_enrich_props`. `/prizepicks/audit`
  and `/dk` do not. *Done when:* service tests with a mocked session show
  that a missing row, a v4 row while `PROJECTION_VERSION` is v3, and a
  wrong-rule row each leave every `adopted_pick` null and every other field
  identical. A v3 row adopting one slice sets `adopted_pick` on exactly the
  matching line. The router test for `/props/prizepicks` still passes with no
  stored row.
- [x] **Step 6 - Web board ranking** - `types` gains `AdoptedPick` and
  `PropLine.adoptedPick?: AdoptedPick | null`. In `tennisPropBoard.ts`,
  `compareLines` puts adopted lines first by margin descending (ties by the
  48f order), and the bucket rule lets an adopted goblin into `rateable`.
  `trustLabel` gains `Pick` for adopted lines. In `tennisPropCards.ts`, an
  adopted card has `pickLabel` `OVER` / `UNDER` and a positive tone, and an
  unadopted card is unchanged. `TennisPropTable` renders the side and margin
  in `--positive` for adopted rows only. *Done when:* Vitest cases pass:
  - with no `adoptedPick` anywhere, board order equals the order 48f's tests
    pin;
  - an adopted line with a later start sorts ahead of an earlier unadopted
    one;
  - two adopted lines order by margin;
  - an adopted goblin is in `rateable`;
  - an unadopted card has no side label and no tone.
  *Build-time addition:* an adopted goblin also passes the "hide alternates"
  filter, so a pick is never hidden behind the toggle. An adopted under is
  green, not red: it is a pick, not a negative.
- [x] **Step 7 - Match page, Intelligence page, copy** - `TennisMatchDetail`
  prop rows show an adopted pick's side and margin in `--positive` and lead
  the list (through `compareLines` / `propRank`). `unifiedTennis.ts` keeps
  board order, so adopted lines lead there too. Update the
  `howItWorksContent.ts` line. *Done when:* `npm --prefix web run build`
  passes, and screenshots of the board and a match page (Vite dev server,
  responses generated by the API's own code as in 48f, since this container
  has no database) show two things. With no adoption, nothing changed from
  `master` and no green on any PrizePicks row. With one synthetic adopted
  slice, exactly the matching rows lead and are green.
  *Build-time change:* the linked match page is `/tennis/match/:id`
  (`MatchPropsPanel`), which builds its rows with `buildTennisPropBoard`, so
  adopted lines lead there with no extra code. Its "never picks" note is
  reworded. The evidence drawer (`TennisPropEvidencePanel`) shows the
  adopted side and margin in green as the table does. `TennisMatchDetail`
  (the inline slate detail, shown only without an analysis page) gets the
  same green cell. The board's "gray, unranked" stat label reads "ranked
  only if adopted".
- [x] **Step 8 - Workflow, docs, Verify** - add `.github/workflows/tennis-prop-adoption.yml`
  with `workflow_dispatch` only (inputs `version`, `dry_run` defaulting to
  true) and the same Python setup as `tennis-prop-lines.yml`. Add the
  `AGENTS.md` Ingest line and the `docs/commands.md` section, both saying the
  first real run needs a separate yes. Update the employer guide if it
  exists locally (never staged). *Done when:*
  `npm --prefix web run verify && cd api && python -m pytest` passes and the
  workflow file parses (`python -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))"`).

## Files / areas

- New: `api/app/core/tennis_prop_adoption.py`,
  `api/app/ingest/tennis_prop_adoption.py`,
  `api/app/services/tennis/prop_adoption.py`,
  `api/tests/test_tennis_prop_adoption.py`,
  `api/tests/test_tennis_prop_adoption_service.py`,
  `.github/workflows/tennis-prop-adoption.yml`
- Changed (API): `app/repositories/props.py` (three columns, three `Prop`
  fields), `app/schemas/props.py` (`AdoptedPick`, `PropLine.adopted_pick`),
  `app/routers/props.py` (`get_prizepicks_props` only), and the props
  repository and router tests
- Changed (web): `src/types/` (the `PropLine` type), `utils/tennisPropBoard.ts`,
  `utils/tennisPropCards.ts`, `utils/tennisMatch.ts`, `utils/unifiedTennis.ts`
  (only if its ordering does not already flow from `compareLines`),
  `components/tennis/TennisPropTable.tsx`,
  `components/tennis/TennisMatchDetail.tsx`, `pages/howItWorksContent.ts`,
  plus their tests
- Docs: `AGENTS.md`, `docs/commands.md`
- Read, not changed: `app/core/tennis_prop_check.py`,
  `app/core/prop_ranking_rule.py`, `app/backtest/tennis_prop_check.py`,
  `app/repositories/report_snapshots.py`,
  `app/services/tennis/prop_snapshots.py` (48c's)
- No migration: `report_snapshots` (0045) already exists.

## Data / contracts

### Stored payload (load-bearing; a later `/tennis/model` display reads it)

`report_snapshots` row: `report = "tennis_prop_adoption:<projection_version>"`,
`season = 0`. Tennis grading spans seasons, and the PK needs an integer, so
0 is a fixed marker, as the NFL slate puts its week in the report name.

```json
{
  "rule": "tennis-props-check-v1",
  "projectionVersion": "props-v3",
  "asOf": "2026-11-30",
  "computedAt": "2026-11-30T13:05:00Z",
  "finishedWeeks": 5,
  "decidedSlices": 2,
  "adopted": [
    {"stat": "aces", "tour": "ATP", "anchor": "book", "oddsType": "standard", "side": "over"}
  ]
}
```

- `adopted` is the only field the request path trusts. An empty list is
  valid and means "nothing adopted".
- No per-slice `n`, hit rate or SE is stored, so the board's data never
  carries a running hit rate (48e's "undecided slices show no hit rate").

### API field (load-bearing for the web)

`PropLine.adopted_pick: AdoptedPick | None` (camelCase `adoptedPick`), null
unless the line's slice is adopted and it survives the ladder collapse:

| Field | Type | Meaning |
|---|---|---|
| `side` | `"over" \| "under"` | 27i `pick_side` on push-excluded P |
| `probability` | float | push-excluded P(side) |
| `break_even` | float | `BREAK_EVEN_BY_ODDS_TYPE[odds_type]` |
| `margin` | float | `probability - break_even`, the ranking key |
| `rule` | str | `tennis-props-check-v1` |
| `projection_version` | str | `props-v3` today |

`confidence` stays null, and `recommendation`, `p_over` and `break_even_pct`
are unchanged. Snapshots never store `adopted_pick`.

## Testing

- Steps 1-3: pure unit tests on synthetic lines and results. `now` and
  `as_of` are passed in, never read from the clock. The parity test is the
  guard that the live path and the grader cannot drift.
- Step 4: repository SQL test with the session mocked.
- Step 5: service tests with the snapshot read mocked, plus the existing
  router test.
- Steps 6-7: Vitest on the board and card utils. Components are checked by
  build and screenshots, per the Testing standard.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Blind.** Do not query `prop_projection_snapshots`, run either CLI
  against a database, or open any v3 or v4 outcome. This container has no
  database anyway. Synthetic adopted sets in tests and screenshots must be
  obviously synthetic (for example `aces / ATP / book / standard / over`),
  and none is ever written to a real `report_snapshots` row.
- **Never edit 48e's rule module or the shared 27i modules.** If the live
  path seems to need something they don't export, import the public pieces
  and pin parity with a test. If parity cannot be had without an edit, stop
  and ask, since any rule change is a new rule name.
- **Never touch 48c's files.** 48c may merge first and add
  `SIM_PROJECTION_VERSION`. 48g reads only `PROJECTION_VERSION`, so nothing
  changes here.
- Signal colors (invariants reviewer, rule 8): green only on a row with a
  non-null `adoptedPick`. Run `/invariants-review` before `/complete`.
- Layering: SQL in `repositories/`, the snapshot read and post-pass in
  `services/tennis/`, and the router only calls them.
- No em dashes in new code, docs, workflow or commit messages.
- The first real run of the writer (or of the 48e grader) is the owner's,
  after merge, with a separate yes in chat.

## Decisions (owner accepted all four recommendations, 2026-10-29)

1. **Best picks.** Should an adopted line also become a best pick and an
   angle again? *Recommended: no, not in 48g.* The board and match page are
   enough to make the edge visible, and best picks has its own ranking
   across market types that would need a cross-type rule. The follow-up
   would be a small later item.
2. **Schedule.** *Recommended: `workflow_dispatch` only, with `dry_run`
   defaulting to true.* A cron would grade real v3 outcomes on its own after
   merge, before your separate yes. Once you have run it once, a weekly cron
   (Tuesday, after the 3-day maturity) can be added as its own small change.
3. **Ladders.** *Recommended: only the surviving rung is a pick*, and the
   other rungs stay gray. That is the rung the grader counted, so the board
   never shows three picks for one decision.
4. **Board placement.** *Recommended: adopted lines lead the existing
   rateable bucket*, rather than going in a separate "Picks" section. The
   section would sit empty every day until something adopts.

## Results

- **Built, nothing adopted yet.** The grade has never run on real data, so no
  `tennis_prop_adoption:props-v3` row exists and the board, match page and
  drawer read exactly as on `master`: every PrizePicks line gray and unranked.
  No v3 or v4 snapshot or outcome was read while building; this container had
  no database.
- **Served version:** `PROJECTION_VERSION` (`props-v3`) only. A `props-v4`
  row (48c, shadow) is rejected on read, so v4 verdicts are never served
  while the board shows v3 numbers.
- **Request path:** one small `report_snapshots` point read plus a pure
  post-pass on `/tennis/props/prizepicks`. A missing, malformed, wrong-rule
  or wrong-version row serves as "nothing adopted", never a 503. A DB error on
  that read still fails the route like any other query in it (invariants
  review note, left as is).
- **Parity with 48e:** live lines go through 48e's own `to_frozen_call`,
  27i's `to_pick` and `one_pick_per_bet`, then `slice_key`, so no exclusion
  logic is copied. `tennis_prop_check.py`, `prop_ranking_rule.py`,
  `prop_ranking_check.py` and every 48c file are unchanged.
- **Build-time changes:** no `live_line` helper (Step 1); `CASE` rather than
  `COALESCE` for the resolved match's tours (Step 4); an adopted goblin shows
  with alternates hidden and an adopted under is green, not red (Step 6); the
  match page is `MatchPropsPanel`, plus the evidence drawer and inline slate
  detail (Step 7). The writer imports `to_frozen_lines` from
  `app/backtest`, the first ingest module to do so, rather than copy it.
- **Screenshots:** board and match page with nothing adopted and with two
  synthetic adopted slices (`aces / ATP / book / standard / over` and the
  goblin over), built from the API's own schema and `apply_adoption` and
  served by Playwright; adopted side and margin compute to `--positive`
  (rgb 0, 200, 5), unadopted rows gray.
- **Tests:** 46 new API tests (31 live adoption and parity, 13 payload, 2
  summary) plus 12 service and route and 2 repository tests; 7 new Vitest
  cases. Verify: `npm --prefix web run verify && cd api && python -m pytest`
  with `DATABASE_URL=postgresql://localhost/ci` (988 web, 4,935 API passed).
- **Invariants review:** clean.
- **Not done here:** the first real run of `tennis_prop_adoption` (owner's
  separate yes; dry run included, since it reads settled outcomes), a weekly
  schedule, best picks for adopted lines, and showing verdicts on
  `/tennis/model`.
