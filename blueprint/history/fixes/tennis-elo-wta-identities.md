# Current Feature

**Feature:** Candidate tennis ELO blocked by four WTA identity conflicts
**Type:** Fix
**Branch:** `fix/tennis-elo-wta-identities`

## The problem

The `Daily Candidate Tennis ELO` job in `tennis-box-scores.yml` fails at
"Refresh isolated candidate ratings" (runs #5 and #6).
`python -m app.ingest.tennis_elo --write` finds identity conflicts and prints
`BLOCKED, 0 inserted`, then exits 1 by design. The later validate and
cache-share steps are skipped. A local dry run on 2026-10-28 reproduced it.
Nothing is written, and the served ELO is unaffected. Each blocked UTC day
leaves no candidate snapshot, and a missed day cannot be backfilled. That gap
thins 41b's shadow comparison.

Conflicts reported by `map_players` (`app/ingest/tennis_elo.py`), all WTA:

| Kind | Provider | Local |
|---|---|---|
| One provider ID, two spellings, two local players | `223410` "Georgia Pedone" / "Giorgia Pedone" | 2856 and 79460 |
| One local player, two provider IDs | Alevtina Ibragimova `260581`, `332575` | 2463 |
| One local player, two provider IDs | Teodora Kostovic `266640`, `267020` | 2433 |
| One local player, two provider IDs | Xinran Sun `266647`, `335958` | 79903 |

The second ID for each of the last three appears only in the newest files.
This matches the renumbering that the existing registry rows already record.

## The fix

Reviewed data rows only. No code, schema or workflow change.

- `api/app/ingest/data/tennis_elo_identities.csv`: one `verified` alias row
  per renumbered player, mapping the raw ID to a canonical ID. Default to the
  ID with the longer history as canonical. Evidence is written like the
  existing rows: exact or normalized name, country, implied birth date where
  available, and never in the same event or against the same opponents. Add
  a draw or profile link where one exists.
- `api/app/ingest/data/tennis_elo_local_overrides.csv`: one `verified` row
  pinning `WTA,223410` to the correct local Pedone. Choose the record that
  carries her `livetennis_id` and recent matches. Record the other record as a
  probable duplicate in the evidence, without merging or deleting it (a local
  player merge is a separate change).
- If any pair cannot be confirmed as the same person, its row stays
  `proposed` (counted, never applied). The run then remains blocked, and this
  spec reports why instead of forcing a link.

Must not break:

- The registry rules in `app/core/tennis_elo.py`: no alias chains, no
  duplicates, no canonical ID that is itself an alias, one local player per
  override.
- Production ELO (`player_elo`), the ensemble, and any stored candidate or
  comparison row. Rows already stored stay immutable.
- 41b's pre-registered rule and sample. Linking more players adds candidates
  from today on. It does not rescore or backfill earlier days.

Changing either CSV changes the workflow's cache key, so the next run
downloads fresh originals. That is intended.

## Build steps

- [x] **Step 1 - Gather evidence (read-only)** - for each pair, compare
  provider rows (name, country, birth/age, events, opponents, dates) from
  the cached TennisMyLife files. Compare local records 2856, 79460, 2463,
  2433 and 79903 (name, birth date, country, `livetennis_id`, match count,
  latest match). Present a table of proposed rows with evidence for owner
  review.
  *Done when:* the owner approves each row as `verified` or `proposed`.

- [x] **Step 2 - Registry rows** - add the approved rows to both CSVs.
  *Done when:* `python -m app.ingest.tennis_elo` (dry run) reports
  `identity conflicts: 0` and `DRY RUN, 0 inserted`, rather than `BLOCKED`,
  and `pytest tests/test_tennis_elo_identities.py` passes.

## Verify

- Local dry run: zero conflicts; tracked candidates rise by up to four
  players. The rating rows for the linked players show the merged history.
- Full Verify command passes:
  `npm --prefix web run verify && cd api && python -m pytest`.
- After merge and an approved push: the next scheduled run, or a manual
  dispatch with `job: tennis-elo`, goes green through "Share original daily
  ELO inputs". A real `--write` happens only in that workflow, never locally.

## Outcome (2026-10-28)

- Cause, refined in Step 1: not renumbered histories. TennisMyLife's
  `wta_ongoing_tourneys.csv` re-emitted matches already in the annual files
  (identical `tourney_id`, `match_num`, opponents, scores, ages) under new
  player IDs, and 2026-10-26 Guangzhou appeared only under the new IDs.
  Pedone was one provider ID spelled two ways, matching two local records.
- Rows added: aliases `332575->260581`, `267020->266640`, `335958->266647`;
  local override `WTA,223410 -> 79460`.
- Local dry run: identity conflicts 4 -> 0, ambiguous 7 -> 0, tracked
  candidates 1550 -> 1554, replay players 2688 -> 2685, `DRY RUN, 0 inserted`.
  `tests/test_tennis_elo_identities.py` 22 passed; full Verify passed (web
  typecheck, tests and build; API 4,668 passed).
- Pending: GitHub runner acceptance after an approved push. Blocked UTC days
  before then have no candidate snapshot and cannot be backfilled.
- Follow-up, not done here: local 2856 (Georgia Pedone, no matches) still
  receives the daily TennisAbstract ELO while her matches use 79460, whose
  only ELO row is 2026-04-20, so served Pedone predictions likely read a stale
  ELO. A local player merge needs its own `/fix`. Birth-date disagreements
  (79460, 79903) were recorded, not corrected.
