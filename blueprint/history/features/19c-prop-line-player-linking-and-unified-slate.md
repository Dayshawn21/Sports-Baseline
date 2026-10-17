# Feature: Prop-line player linking and unified NFL slate

**From build-plan:** feature 19c
**Status:** complete

## Goal

Link PrizePicks prop lines to `nfl_players` and `nfl_games`, then merge `/nfl` and
`/nfl/prospects` into one slate-centric page that shows our baseline, the market's
line, and the edge between them on a single row.

Today those are two disconnected pages. `/nfl` knows a player's historical
baseline but not what he is priced at; `/nfl/prospects` knows the price but has no
opinion. Neither is actionable alone, and the edge column that would make them
actionable cannot exist until a prop line can name a player we have stats for.

## In scope

- Capture the provider's team and position, which the parser currently resolves and then discards.
- Normalize NFLverse and PrizePicks names to a comparable key, including suffixes (`Jr.`, `III`) and punctuation.
- An `nfl_player_aliases` table for matches the automatic pass cannot make or gets wrong.
- Resolve `nfl_prop_lines.player_id` and `game_id` at ingest, leaving them NULL rather than guessing when confidence is low.
- Edge as a pure function of baseline projection versus line.
- One merged page at `/nfl`, organized by game, with unmatched lines visible in a labeled section rather than silently dropped.
- A staleness warning on every edge while baselines come from a season other than the line's.

## Out of scope

- **Loading 2025/2026 NFLverse data.** That is 19d. This feature must work correctly against 2024 data and say plainly that the baseline is stale.
- **A real projection model.** Naive averages stay; that is 19e.
- **Converging the tennis and NFL stacks.** That is 17.
- **Betting recommendations, Kelly sizing, or writing to `bets`.** Display edge only.
- **Fixing `nfl_players.team_id` last-write-wins.** Noted as a known defect; do not rewrite the historical baseline query here.
- **`nfl_prop_predictions` / `nfl_prop_results` persistence.** Compute edge on read.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Capture provider team and position.** `_parse_projections` in `prizepicks.py` already reads `position` from the `new_player` include and drops it. Return `player_team` and `player_position` alongside the existing keys, and persist both into `nfl_prop_lines.raw_json`. Additive only; tennis callers ignore the new keys. *Done when:* a fresh `prizepicks_nfl` run stores a non-null team and position for a known player, and a parser unit test asserts both are extracted from a fixture payload.

- [x] **Step 2 - Name normalization, pure.** New `app/core/nfl_names.py`: turn `"Michael Pittman Jr."` and `"M.Pittman"` into the same key. Strip suffixes (`Jr.`, `Sr.`, `II`-`IV`), punctuation, and case; emit first-initial + surname. No DB, no I/O, per the `core/` purity rule. *Done when:* unit tests cover suffixes, hyphenated surnames (`Smith-Schuster`), `St. Brown`, and apostrophes, and confirm that `Jameson Williams` and `Javonte Williams` produce the *same* key (proving the key alone cannot disambiguate).

- [x] **Step 3 - Alias table.** Migration `0018` adding `nfl_player_aliases` (`alias_name`, `alias_name_norm` unique, `source`, `nfl_player_id` FK cascade), mirroring the tennis `player_aliases` shape. *Done when:* `alembic upgrade head` applies cleanly, and a manually inserted alias resolves in a repository test.

- [x] **Step 4 - Resolution, pure.** A function taking a provider name plus team and position and a candidate player list, returning a match or `None` with a reason. Order: exact alias, then normalized key when unique, then normalized key plus team or position to break ties. Never guess when still ambiguous. *Done when:* unit tests prove a unique key matches, three `J.Williams` resolve only with position or team, an unmatchable rookie returns `None` with a reason, and no test asserts a guess.

- [x] **Step 5 - Wire resolution into ingest.** Populate `player_id`, and `game_id` via the resolved player's team and the line's `start_time`. Report counts (matched / ambiguous / unmatched) at the end of a run. *Done when:* a fresh run prints the three counts and links at least 60% of full-game lines (the naive key already reached 54 of 87 provider names before suffix handling or tie-breaking), and every remaining NULL carries one of the reasons from Step 4.

- [x] **Step 6 - Backfill the lines already stored.** The 1,221 rows currently in `nfl_prop_lines` all have NULL `player_id`, and ingest only ever INSERTs, so they would stay unlinked forever while new rows resolve. Add a `--relink` flag that re-runs resolution over stored rows without refetching from the provider. *Done when:* running it against the existing table links the same share as a fresh run, and running it twice changes nothing the second time.

- [x] **Step 7 - Edge calculation, pure.** `edge(projection, line)` in `app/core/nfl_projection.py`, plus a staleness flag when the baseline season differs from the line's season. *Done when:* unit tests cover over, under, exact-equal, and the stale-season flag.

- [x] **Step 8b - Separate real lines from alternate lines.** *Added during Step 8, when live data showed the problem.* PrizePicks publishes a ladder per player per market: `goblin` lines set deliberately low, `standard` (the market's actual estimate), and `demon` set deliberately high, each with an adjusted payout. Stored counts are 1,399 demon, 669 goblin, 617 standard. Ranking them together puts a 149.5 demon receiving-yards line at the top of the board with a -75 edge that reflects the payout structure, not a mispricing. Migration `0019` adds `nfl_prop_lines.odds_type` (mirroring tennis `props.odds_type`), ingest captures it, `--relink` backfills it from `raw_json`, and edge is computed only for `standard`; others carry a `non_standard_line` flag with `edge = null`. *Done when:* the slate's top-ranked lines are standard only, goblin and demon rows appear with a null edge and the flag, and a unit test covers the flag.

- [x] **Step 8c - Repair two stat columns that never loaded.** *Added during Step 8, when a zero projection ranked first.* `nfl_player_weekly_stats.passing_attempts` and `.touchdowns` are zero across all 5,333 rows: the parser reads `passing_attempts` and `fantasy_tds`, neither of which exists among the CSV's 53 columns, and `_as_int(None)` returns 0 silently. Read `attempts`, and sum `passing_tds`, `rushing_tds`, and `receiving_tds`. Re-import 2024 and relink. Strictly an item 19a defect, repaired here because it puts a fabricated QB edge at the top of the board this feature builds. *Done when:* both column sums are non-zero and position-plausible (QBs carry the attempts, all three positions carry touchdowns), the fabricated passing-attempts edge is gone from the slate, and a parser test covers both fields.

- [x] **Step 8 - Unified endpoint.** One `/nfl/slate?season=&week=` returning games, each with players carrying baseline, any linked line (market, segment, line), and edge. Include unlinked lines in a separate `unmatched` array. Keep `/nfl/games`, `/nfl/projections`, and `/nfl/prospects` working so the UI can move in one step. *Done when:* the endpoint returns linked rows with a numeric edge and a populated `unmatched` array, verified against the running API.

- [x] **Step 9 - Merged page, structure only.** Rewrite `/nfl` around the slate: games as sections, players beneath, showing baseline and any linked line with its segment tag. No edge column yet. *Done when:* `/nfl` renders games with players and their lines from `/nfl/slate`, and `npm run build` passes.

- [x] **Step 10 - Edge column and warnings.** Add edge, sort by absolute edge, add the "Unmatched provider lines" section, and the stale-baseline warning. *Done when:* a row shows baseline, line, and edge together; unmatched lines are visible and labeled; the stale-season warning appears while 2024 baselines are priced against 2026 lines.

- [x] **Step 11 - Retire the second page.** Point `/nfl/prospects` at the merged page (redirect), drop it from the nav, and delete `NflProspectsPage.tsx` once nothing imports it. *Done when:* the nav shows one NFL entry, an existing `/nfl/prospects` link still lands somewhere sensible, and `npm run build` passes with no unused-import or dead-file warnings.

## Files / areas

| Path | Change |
|---|---|
| `api/app/ingest/prizepicks.py` | return team and position (additive) |
| `api/app/core/nfl_names.py` | new, pure normalization |
| `api/app/core/nfl_projection.py` | add `edge` and staleness flag |
| `api/app/db/migrations/versions/0018_*.py` | new `nfl_player_aliases` |
| `api/app/repositories/nfl.py` | alias lookup, slate query |
| `api/app/ingest/prizepicks_nfl.py` | resolve and store linkage |
| `api/app/routers/nfl.py`, `schemas/nfl.py` | `/nfl/slate` |
| `web/src/pages/NflIntelligencePage.tsx` | becomes the merged slate |
| `web/src/pages/NflProspectsPage.tsx` | removed in Step 9 |
| `web/src/{api,hooks,types}/nfl.ts` | slate types and hook |

## Data / contracts

**Load-bearing, because 19d, 19e, and NBA will all touch it:**

- `nfl_player_aliases` mirrors tennis `player_aliases` deliberately, so item 17 can converge them rather than reconcile two designs.
- The slate response shape is what 19e's real model and any future NBA slate will fill. Make `projection` a nullable number and `edge` nullable, so "no baseline" and "no line" are representable without sentinel values.
- Resolution returns a **reason** on failure, not just `None`. The props audit view exists in tennis for exactly this; NFL will want the same.

## Testing

`pytest` and `vitest` are both real, so the test gate is on: Steps 1, 2, 4, and 7 are pure logic and must ship tests in the same diff.

- **Step 2** - `api/tests/test_nfl_names.py`: suffixes, hyphens, `St. Brown`, apostrophes, and the deliberate `J.Williams` collision.
- **Step 4** - `api/tests/test_nfl_resolution.py`: unique match, tie broken by team/position, unresolvable returns a reason. Table-driven.
- **Step 7** - extend `api/tests/test_nfl_projection.py`: edge sign, zero edge, stale-season flag.
- **Steps 5, 6, 8** - verify against the running API and real ingest counts, not unit tests. Step 6's idempotency claim needs an actual second run, not an assertion about one.
- **Steps 9, 10, 11** - browser and `npm run build`.

Do not write tests for React components or route integration.

## Notes for the AI

- **`core/` purity is load-bearing.** Steps 2, 4, and 6 take plain arguments and return plain values. No DB, no I/O. Step 4 takes a candidate list, it does not query for one.
- **Repositories own SQL.** The slate query belongs in `repositories/nfl.py`, never in the router.
- **Never guess a player match.** A wrong link produces a confident, wrong edge, which is worse than a blank. Leave NULL and report the reason.
- **Do not present a stale edge as actionable.** Baselines are 2024; lines are 2026. The warning is required, not decorative.
- **Additive parser change only.** `_parse_projections` is shared with tennis. Add keys; do not rename or remove.
- **No em dashes** in generated content, per `coding-standards.md`.
- Known adjacent defects, explicitly *not* this feature's job: `nfl_players.team_id` is last-write-wins, and `/nfl/projections` emits all 9 markets per player so WRs carry `passing_yards: 0.0`.
