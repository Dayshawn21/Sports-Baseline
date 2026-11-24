# Feature: Ask Lineform tools and scaffolding

**From build-plan:** feature 47a (parent 47, Ask Lineform)
**Status:** complete (2026-10-27)
**Branch:** `feature/47a-ask-lineform-tools`

## Goal

Build everything Claude will need to answer questions about Lineform, short of
calling Claude: the `anthropic` dependency and settings, six tools that read
the existing service layer, compact tool results that cite a Lineform page and
label every signal honestly, and the system prompt. 47b's loop then only has to
send messages and dispatch tool calls to what this feature provides.

This is also a learning feature for the owner. Each step's review explains the
AI-engineering idea behind it: tool schemas, why results are trimmed, and why
the signal label is explicit.

## In scope

- `anthropic` pinned in `api/requirements.txt`. New `Settings` fields:
  `anthropic_api_key` (from `ANTHROPIC_API_KEY`, default empty),
  `ask_model = "claude-haiku-5-5"`, `ask_max_tokens = 1024`,
  `ask_max_tool_iterations = 5`.
- Pure Lineform path builders for every page a tool cites.
- Moving the tennis best-picks assembly out of `routers/tennis.py` into a
  service, with no behaviour change, so a tool can call it without a `Request`.
- Six tools. Each has a Pydantic input model (its JSON schema is the tool's
  `input_schema`), a description written for the model, and an async executor
  that calls existing services directly:
  `get_slate`, `get_top_props`, `get_game_detail`, `get_player`,
  `get_model_track_record`, `find`.
- Pure trimming functions that turn each service response into a small,
  model-readable result with `url` and `signal` on every row.
- A tool registry (definitions list plus name-to-executor dispatch) and the
  system prompt text.
- A developer CLI, `python -m app.services.ask.preview <tool> '<json>'`. It runs
  one tool against the local database and prints the exact result JSON and its
  size, so the owner can see what the model will see.

## Out of scope

- Calling the Anthropic API, and the tool loop itself (47b, which the owner writes).
- `POST /ask`, SSE and any web code (47c).
- Rate limits, spend cap and cost logging (47d). The evals (47e).
- NFL in `get_top_props`. The NFL board ranking lives in
  `web/src/utils/nflSlate.ts` and is not ported to Python in v1.
  NBA in `get_player` (there is no NBA player page). NHL in every tool.
- Moving the props-router enrichment helpers (`enrich_with`, `_fetch_*`) out
  of `routers/props.py`. The moved best-picks service keeps importing them
  lazily, as the router does today and as `bankroll_builder.py` already does
  from `routers/tennis.py`. Cleaning that up is a separate `/fix`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Dependency, settings and page paths** - pin `anthropic` (latest
  release, checked against the `claude-api` reference at build time). Add the
  four `Settings` fields. Add `app/core/ask_links.py` with pure builders:
  `slate_path(sport, date|week)`, `game_path(sport, id)` (tennis uses
  `/tennis/match/:id`), `player_path(sport, id)`, `model_path(sport)`,
  `board_path(sport, date)`. Every path is the router path (no `#`); the web
  adds the hash in 47c. *Done when:* `pip install -r requirements.txt` succeeds,
  `Settings()` loads with no Anthropic key set, and `test_ask_links.py` pins
  every builder against the routes registered in `web/src/routes/sportPages.tsx`.

- [x] **Step 2 - Move tennis best picks into a service** - move
  `_build_best_picks`, `_overlay_live_moneyline`, `_slate_predictions` and
  `_target_dates` into `app/services/tennis/best_picks_response.py`. Their
  signatures take `registry` instead of `Request`. The router and
  `bankroll_builder.py` call the new module; the props-router helper imports
  stay lazy. *Done when:* the full API suite passes unchanged, a fixture-built
  best-picks response is byte-identical before and after (captured by a test
  written first, against the old code), and `routers/tennis.py` no longer
  defines those functions.

- [x] **Step 3 - Tool input models and result envelope** - `app/schemas/ask.py`
  holds one Pydantic input model per tool (see Data / contracts), the
  `Sport` literals each tool accepts, and the `ToolResult` envelope.
  `tool_definitions()` returns the Messages API tool list (`name`,
  `description`, `input_schema` from `model_json_schema()`). *Done when:*
  `test_ask_schemas.py` shows that every definition's schema rejects an
  unsupported sport (for example `nhl`, or `nfl` for `get_top_props`), that
  limits are clamped by `le=`, and that no definition exceeds the agreed
  description length.

- [x] **Step 4 - Pure trimmers for slates and top props** - in
  `app/core/ask_results.py`: `trim_nba_slate`, `trim_nfl_slate`,
  `trim_tennis_slate`, `trim_nba_gaps`, `trim_tennis_picks`. Each takes
  plain mappings or dataclasses (no DB) and returns the result rows. Rules:
  times as CT strings plus ISO UTC; at most 20 games and 10 props; `signal`
  per row from one function, `signal_for(sport, kind)`; `truncated` set
  when rows were dropped. *Done when:* tests cover each trimmer on
  fixtures, every row has `url` and `signal`, NBA and NFL rows are always
  `reference_only`, tennis picks are `pick`, a tennis moneyline row can
  never be a `pick`, and each serialized fixture result stays under
  12,000 characters.

- [x] **Step 5 - Executors: `get_slate`, `get_top_props`, `find`** - in
  `app/services/ask/tools.py`, with a `ToolContext` dataclass (`db`,
  `registry`, `now`, `production`). Executors call: NBA `build_slate` and
  `build_slate_gaps`; NFL `get_current_week` then `cached_slate_json`
  (production reads `report_snapshots` and never builds); tennis
  `cached_predictions` and the Step 2 best-picks service. `find` matches a
  folded name against that slate's teams, players and games. Missing
  data (no games, 503-equivalent `None`) returns a result with an explicit
  `note`, never an exception. *Done when:* each executor runs through the
  preview CLI against the local database for today, and unit tests cover
  `find`'s pure matching (accents, partial surname, ambiguity) and the
  empty and unavailable paths with stubbed services.

- [x] **Step 6 - Executors: `get_game_detail`, `get_player`,
  `get_model_track_record`** - NBA `build_game_detail` plus `build_props`
  (standard lines ordered by player then market, capped at 20, still
  labelled reference; never sorted by gap, since NBA game-page props are
  unranked under 20g2; an optional `player_id` input returns one player's
  lines of every payout type); NFL `build_game_detail` plus the stored
  slate's game (market, muted model, props) and that week's
  `build_game_notes` entry; tennis `build_match_detail`; NFL and tennis `build_player_detail`;
  track records: NBA `get_ranking_record`, NFL v4 and Rec Targets
  `get_ranking_record` plus `get_clv_record`, tennis
  `get_prediction_grading` plus `get_tier_grading`. Each slice reports
  verdict, n, hit rate, SE and break-even, plus a plain `meaning`
  (`insufficient` = still accruing, not a pick). Trimmers go in
  `core/ask_detail.py` (split from `ask_results.py` for size) with tests. *Done when:* each runs through the preview CLI,
  and tests show an unknown game or player id returns a `not_found` note and
  every trimmed track-record result stays under 12,000 characters.

- [x] **Step 7 - Registry and system prompt** - `app/services/ask/prompt.py`
  holds `SYSTEM_PROMPT`. `tools.py` exposes `TOOLS` (definitions) and
  `async def run_tool(name, raw_input, ctx) -> ToolResult`, which validates
  with the input model and raises `UnknownToolError` or
  `ToolInputError` for 47b to turn into `is_error` results. The prompt
  covers: answer only from tool results; say when the data does not cover
  the question; never call a `reference_only` or rejected signal a pick, and
  use the app's words ("reference", "gap", "accruing"); cite every number
  with a markdown link to the row's `url`; keep it short; today's date and
  CT time arrive in the user turn, not the prompt, so the prompt stays
  cacheable. *Done when:* tests cover unknown-name and bad-input raises and
  that every name in `TOOLS` dispatches, and the owner has read the prompt
  and approved it.

- [x] **Step 8 - NBA market filter before the digest ranking** (invariants
  review P3) - `get_top_props(sport=nba, market=...)` filtered the digest's
  one-line-per-player output by market, so a player whose largest gap is in
  another market vanished from that market's list. Filter the candidates by
  market before `rank_slate_gaps`, which stays unchanged; the page's call
  (no market) is byte-identical. *Done when:* a test shows a player whose
  biggest gap is in points still appears for assists, and the no-market
  output is unchanged.

## Files / areas

- `api/requirements.txt`, `api/app/config.py`
- New: `api/app/core/ask_links.py`, `api/app/core/ask_results.py`
- New: `api/app/schemas/ask.py`
- New: `api/app/services/ask/__init__.py`, `tools.py`, `prompt.py`, `preview.py`
- New: `api/app/services/tennis/best_picks_response.py`; changed
  `api/app/routers/tennis.py`, `api/app/services/tennis/bankroll_builder.py`
- New tests: `api/tests/test_ask_links.py`, `test_ask_schemas.py`,
  `test_ask_results.py`, `test_ask_tools.py`, `test_tennis_best_picks_response.py`
- `AGENTS.md` (the preview command and `ANTHROPIC_API_KEY`), and the local
  interview guide if it exists

## Data / contracts

No schema or migration.

**Tool inputs (load-bearing for 47b-47e and the evals):**

| Tool | Input |
|---|---|
| `get_slate` | `sport: nba\|nfl\|tennis`, `date?: YYYY-MM-DD` (NBA Eastern date, tennis), `week?: int` (NFL; default current week), `tour?: ATP\|WTA\|CHALLENGER` (tennis) |
| `get_top_props` | `sport: nba\|tennis`, `date?`, `market?: str`, `limit: int = 5` (1-10) |
| `get_game_detail` | `sport: nba\|nfl\|tennis`, `game_id: int` (tennis match id), `player_id?: int` (NBA/NFL: one player's lines) |
| `get_player` | `sport: nfl\|tennis`, `player_id: int` |
| `get_model_track_record` | `sport: nba\|nfl\|tennis`, `season?: int` |
| `find` | `sport: nba\|nfl\|tennis`, `query: str` (2-60 chars), `date?`, `week?` |

**Result envelope (load-bearing):**

```text
ToolResult
  tool: str
  sport: str
  url: str | None          # the page this whole result came from
  as_of: str               # ISO UTC time the tool ran
  note: str | None         # "no games on this date", "not_found", "unavailable"
  truncated: bool
  data: object             # tool-specific, rows below
row (every row in data)
  url: str                 # most specific page: game, match, player or model
  signal: "pick" | "reference_only" | "none"   # none = plain facts (scores, injuries)
```

`signal` comes only from `signal_for` in `core/ask_results.py`. The rule
matches the app: a tennis pick is `pick` only when it is a priced best bet
under the slate's green rule (`isPricedBestBet` in
`web/src/utils/unifiedTennis.ts`, ported as `is_priced_best_bet` with the same
thresholds); unpriced tennis angles are `reference_only`; tennis moneyline is
never a pick (`MONEYLINE_PICKS_ENABLED` is False); every NFL and NBA
projection, gap and P(over), and every tennis win probability, is
`reference_only`. (Refined in Step 4: the draft called every tennis best pick
a `pick`.)

## Testing

- The test gate is on: Steps 1 and 3-7 ship pytest tests for their pure
  logic (paths, schemas, trimmers, signal rule, `find` matching, dispatch).
  Step 2 ships the byte-identical regression test.
- Executors are verified through the preview CLI against the local database.
  Their DB paths are covered by the services they call, not new integration
  tests.
- Final gate: the Verify command
  (`npm --prefix web run verify && cd api && python -m pytest`).
- No test calls the Anthropic API or needs `ANTHROPIC_API_KEY`. CI uses a
  dummy `DATABASE_URL` and must stay keyless.

## Notes for the AI

- **Teach as you go.** The owner is learning AI application engineering.
  Each step's review explains the idea in two or three sentences:
  - Step 3: how a tool schema is the model's only contract.
  - Step 4: trimming cuts tokens and cost, and keeps results inside the
    context window.
  - Step 7: the prompt stays static so it can be cached.
- **Don't write 47b's loop.** `run_tool` is the boundary; the loop is the owner's.
- **Same services as the pages.** Never call the API over HTTP or rebuild a
  heavy report. NFL slate goes through `cached_slate_json` so production
  respects the 512 MB rule.
- **Sport filters and provider filters** are inherited from the services
  called; add no SQL. If a tool seems to need new SQL, it goes in a
  repository and is raised at review first.
- **Signal honesty is the invariant this feature exists to protect.** NFL and
  NBA gaps stay reference, NBA P(over) is assists only, and tennis
  moneylines are not picks. Run the `invariants-reviewer` before `/complete`.
- `Settings` reads `ANTHROPIC_API_KEY`; never `os.environ`. The key is never
  logged or returned.
- Load the `claude-api` skill before Step 1's pin and Step 3's tool
  definitions.
- No em dashes in new code, comments or docs.
