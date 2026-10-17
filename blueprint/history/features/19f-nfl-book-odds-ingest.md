# NFL book odds ingest

**Type:** Feature
**From build-plan:** 19f

## Goal

Ingest upcoming NFL game moneyline, spread, and total odds from the existing
Odds-API.io account. Persist each sportsbook snapshot with its two de-vigged
outcome probabilities, linked only to an existing `nfl_games` row. This gives
feature 19e a reliable market-probability input without changing its current
baseline projection behavior.

## In scope

- A bounded, read-only provider inventory capture for American Football that
  records the supported sport parameter, books, market names, and one sanitized
  representative payload shape.
- A new append-only `nfl_game_odds` table and repository functions for game-odds
  snapshots.
- An idempotent NFL odds CLI using the existing `ODDS_API_KEY`, provider request
  and rate-limit conventions, and already-ingested scheduled NFL games as the
  matching source of truth.
- Parsing moneyline, spread, and total markets. Each valid two-sided market
  stores original American odds, its line when applicable, and normalized
  no-vig probabilities.
- Schedule the job after NFL schedule ingest, with the existing GitHub Actions
  secret and no additional provider or credential.

## Out of scope

- NFL player-prop ingest or PrizePicks changes.
- Building an NFL projection model, scoring bets, or changing the NFL slate UI.
  Those belong to 19e.
- Reworking tennis odds ingest or generalizing tables for all sports. Item 17
  owns that convergence.
- Three-way outcomes, in-play odds, alternate lines, historical backfill, and
  a new paid provider tier.

## Data contract

`nfl_game_odds` is an append-only provider snapshot table. It must contain:

| Field | Meaning |
|---|---|
| `game_id` | Existing `nfl_games.id`; unmatched provider events are never stored. |
| `book`, `market` | Provider book plus canonical `moneyline`, `spread`, or `total`. |
| `line` | Spread from the home-team perspective, or the game total; null for moneyline. |
| `first_side`, `second_side` | `home`/`away` for moneyline and spread; `over`/`under` for totals. |
| `first_odds`, `second_odds` | The raw American prices for those exact sides. |
| `first_market_prob`, `second_market_prob` | The two-way no-vig probabilities, which sum to 1 within ordinary float tolerance. |
| `fetched_at`, `raw_json` | Capture time and the minimum raw provider market evidence needed for diagnosis. |

The side labels make total-market probabilities unambiguous and give 19e one
stable contract: use the `home` probability from the latest moneyline row for a
game and book. Missing, malformed, one-sided, unmatched, completed, cancelled,
or live events are logged and skipped, never guessed into a database row.

## Build steps

- [x] **Step 1 - Capture and lock the NFL provider shape.** Add a bounded
  `--inventory-only` path or NFL-specific companion that makes at most one
  American Football events request and one odds-batch request, records the
  actual provider sport key, returned book names, market names, and sanitized
  sample structure in `docs/`. It must reuse the configured key and report
  provider-plan or quota failures clearly.
  *Done when:* the capture has a documented request budget, produces no database
  writes, and tests cover response-shape extraction without a live call.

- [x] **Step 2 - Add the game-odds snapshot contract.** Create an Alembic
  migration and repository helpers for `nfl_game_odds`, with foreign key,
  lookup indexes, side labels, raw American prices, and persisted no-vig
  probabilities. Keep the table separate from `nfl_prop_lines`: a game market
  is not a player prop.
  *Done when:* migration upgrade and downgrade work, and a repository test or
  focused database check proves a snapshot can be written and retrieved in
  newest-first order for a game, book, and market.

- [x] **Step 3 - Parse and orient supported game markets, pure.** Build typed,
  pure parser helpers for the captured Odds-API.io NFL market shape. Normalize
  decimal provider prices to American odds, orient spreads to the stored home
  team, label totals as over/under, and calculate probabilities with the shared
  two-way de-vig helper.
  *Done when:* fixture tests cover home/away reversal, positive and negative
  spreads, totals, malformed prices, missing sides, and prove each accepted pair
  has no-vig probabilities totaling 1.

- [x] **Step 4 - Match scheduled events and persist snapshots.** Implement
  `python -m app.ingest.nfl_odds` using the existing Odds-API.io batching,
  quota floor, logging, and `Settings` access patterns. Match by both normalized
  home/away teams and a bounded kickoff-date window against scheduled
  `nfl_games`; do not use team names alone. Persist only accepted parsed
  markets, retain every configured returned book, and commit once per run.
  *Done when:* mocked integration tests prove correct game and side orientation,
  duplicate-safe reruns, unmatched-event skips, and quota-floor early stop; a
  local dry run reports matched, skipped, and stored counts without exposing a
  secret.

- [x] **Step 5 - Schedule and verify the operational path.** Add the NFL odds
  job to the existing NFL ingest workflow after schedule ingest, using the
  existing secret and a conservative request scope. Document the local command
  in `AGENTS.md`.
  *Done when:* workflow YAML validates by inspection, no new secret is needed,
  API tests and web build/tests pass, and the documented command is runnable
  with only the current environment variables.

## Files / areas

| Path | Change |
|---|---|
| `api/app/ingest/nfl_odds.py` | New NFL-specific provider capture and ingest CLI. |
| `api/app/core/nfl_odds.py` | Typed, pure parsing, orientation, and de-vig helpers. |
| `api/app/repositories/nfl.py` | Snapshot write and latest-market lookup functions. |
| `api/app/db/migrations/versions/0020_nfl_game_odds.py` | New game-odds snapshot table. |
| `api/tests/test_nfl_odds.py` | Parser, event matching, and ingest behavior fixtures. |
| `.github/workflows/nfl-ingest.yml` | Scheduled NFL odds refresh after schedule ingest. |
| `AGENTS.md` | Local NFL odds ingest command. |
| `docs/nfl-odds-market-inventory.md` | Sanitized captured provider capability record. |

## Testing and verification

- New pure parsing and matching logic ships with focused `pytest` coverage.
- Mock all provider calls. The one inventory capture is the only planned live
  request and is bounded before it is run.
- Run `cd api && .venv\\Scripts\\python.exe -m pytest`.
- Run `cd web && npm run test` and `npm run build`.
- Confirm a local CLI dry run logs counts and does not print `ODDS_API_KEY`.

## Notes for the AI

- Keep all SQL in `repositories/nfl.py`; keep `core/nfl_odds.py` free of DB and
  network I/O.
- Do not copy the tennis parser blindly. NFL totals have over/under sides and
  spreads need a home-team orientation rule, both of which must be explicit.
- Do not infer a provider sport key or market names. Step 1 records the actual
  supported payload before the parser is written.
- The persisted no-vig probabilities are load-bearing for 19e. Preserve raw
  prices too, so later calibration work can be audited or recomputed.
- No em dashes in generated content.
