# Feature 24d: Game-line slate

**From build-plan:** feature 24d
**Status:** completed (2026-09-19)

## Final outcome

Every `/nfl/slate` game now carries a nullable `model` block (`nfl-elo-v1`
spread in book sign, home win probability, and the 24b scoring-rating total,
plus the market win probability de-vigged from the displayed book). The NFL
page shows it in a muted strip under the matchup bar with a fixed "display
only, not a pick" caveat; it never feeds an edge, sort, or signal board. This
closes item 24: no game-line signal was adopted, so the model is context only.

Known costs: the total replay adds an all-games query (about 164 ms on a
676 ms slate request), and ratings can be a week stale between a final score
and the Tuesday ELO recompute.

## Goal

Show the model's pre-game spread, home win probability, and total beside the
market for every game on the NFL slate. 24b, 24e, and 24c all failed to beat
closing lines, so by the build plan's own rule this is **display-only**:
context that says what team strength implies, never an edge, a pick, or a
ranking.

## In scope

- A pure game-model line in `core/`: ELO spread and win probability from the
  stored `nfl-elo-v1` ratings, and a total from the 24b scoring rating, with
  the spread converted to the **book** sign convention the slate already shows.
- A nullable `model` block on each `/nfl/slate` game, beside the existing
  `odds` block, including the de-vigged market win probability from the same
  book the slate displays.
- A pure web helper that phrases model versus market in team terms.
- A model strip on the NFL page under the matchup bar, with a fixed caveat and
  mobile layout.

## Out of scope

- Any edge, highlight, sort, or filter driven by the model. The strip must not
  look like a signal.
- Team efficiency (24c), rest, and roof as displayed context. 24c and 24e allow
  it, but the build-plan line names spread, win probability, and total only.
  A later `/fix` can add a team-context row.
- A tuned ELO version. 24b rejected the fitted config, so `nfl-elo-v1` stays
  the stored and displayed rating.
- Storing model totals. They are replayed per request (see Notes).
- Forecast-weather adjustments (the 24e post-hoc hypothesis).
- Tennis, props, and every other page.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure game-model line.** In `app/core/nfl_game_lines.py`, add
  `NflGameModelLine` and `game_model_line(home_elo, away_elo, expected_total,
  home_moneyline, away_moneyline)`. It returns the ELO home win probability,
  the model home spread in book convention (`-elo_margin`, so negative means
  home favored), the model total, and the de-vigged market home probability
  (None when either moneyline is missing), all at `NFL_ELO_V1.home_field`.
  Add `NFL_SCORING_V1 = NflScoringConfig(learning_rate=0.05)` to
  `core/nfl_scoring_ratings.py` as the 24b-fitted rate.
  *Done when:* tests cover a home favorite (probability above 0.5 and a
  negative spread), an away favorite (positive spread), equal ratings (spread
  of exactly minus the home-field points / 25, i.e. -1.92), a missing
  moneyline, and that the spread is the negation of `elo_margin`.

- [x] **Step 2 - Slate API field.** Repository `get_slate_team_elo(db, season,
  week)` returns `{game_id: (nflverse_game_id, home_elo_pre, away_elo_pre)}`
  for `nfl-elo-v1`, only for games with both rows. The NFLverse key is what
  joins the scoring replay, which is keyed by game key, not database id. The
  `/nfl/slate` router replays `get_elo_games` with `NFL_SCORING_V1` for the
  week's expected totals, calls `game_model_line` with the displayed book's
  moneylines, and sets `model` on each game (`NflGameModelSchema`, contract
  below). A game missing either ELO row gets `model: null`.
  *Done when:* a repository test pins the model-version filter, the home/away
  pairing, and that a game with one ELO row is left out; router-helper tests
  in `test_nfl_projection.py` cover a game with ELO and no odds
  (`marketHomeWinProbability` null) and a game with no ELO (`model` null);
  and `GET /nfl/slate?season=2026&week=3` returns a `model` on all 16 games.
  For `2026_03_PHI_CHI`, the printed `marketHomeWinProbability` equals
  de-vigging that game's displayed `odds.homeMoneyline` and
  `odds.awayMoneyline`, and the model `homeSpread` sign matches its
  `homeWinProbability` side.

- [x] **Step 3 - Web types and helper.** Add `NflGameModel` to
  `web/src/types/nfl.ts` and `model` to `NflSlateGame`. New
  `web/src/utils/nflGameModel.ts` with `nflGameModelSummary(model, odds,
  homeTeam, awayTeam)` returning display strings: model spread with the
  favored team (`CHI -2.3`), model total, model win probability, and, when the
  market exists, the market value and a team-phrased gap (`0.8 pts more on
  CHI` for spread and win probability alike, `1.9 over market` for the total;
  under 0.05 reads `Matches market`). Missing market reads
  `No market line`; a null model returns null.
  *Done when:* Vitest covers a home favorite, an away favorite, a pick'em
  (spread within 0.05 shows `PK`), a model that disagrees on the favorite,
  missing spread, missing total, missing moneyline, and a null model.

- [x] **Step 4 - Model strip on the NFL page.** Under `MatchupBar`, render a
  `GameModelStrip`: three cells (Spread, Win prob, Total), each showing model
  beside market with the gap from Step 3, plus a caveat line: "Team-strength
  model, display only. It did not beat closing lines in 2022-2025 testing;
  not a pick." Styling reuses the matchup-bar tokens in `nfl-slate.css`,
  muted rather than accented, with no positive or negative colors. `model:
  null` renders one line: "Model unavailable for this game".
  *Done when:* `npm run build` and `npm run test` pass, and screenshots of
  week 3 at 1440px and 390px wide show the strip under the matchup bar with no
  horizontal scroll, the caveat visible, and no change to the signal boards;
  a game with no stored odds (week 4) shows model values with `No market line`.

## Files / areas

- `api/app/core/nfl_game_lines.py`, `api/app/core/nfl_scoring_ratings.py`
- `api/app/repositories/nfl.py` - `get_slate_team_elo`
- `api/app/routers/nfl.py`, `api/app/schemas/nfl.py`
- `web/src/types/nfl.ts`, `web/src/utils/nflGameModel.ts` (new),
  `web/src/pages/NflIntelligencePage.tsx`, `web/src/pages/nfl-slate.css`
- Tests: `test_nfl_game_lines.py`, `test_nfl_repository.py`,
  `test_nfl_projection.py` (router helpers are tested there),
  `web/src/utils/nflGameModel.test.ts` (new)

## Data / contracts

No schema change.

**`NflGameModelSchema`** on `NflSlateGameSchema.model` (load-bearing: any later
adopted game-line signal extends this block rather than adding another):

| Field (camelCase on the wire) | Type | Meaning |
|---|---|---|
| `modelVersion` | string | `nfl-elo-v1` |
| `homeElo`, `awayElo` | number | pre-game ratings |
| `homeWinProbability` | number | ELO, home field included |
| `homeSpread` | number | **book convention**: negative = home favored, same sign as `odds.homeSpread` |
| `total` | number | scoring-rating expected points |
| `marketHomeWinProbability` | number \| null | de-vigged from `odds.homeMoneyline` / `odds.awayMoneyline` (same book as displayed) |

`model: null` means no pre-game ELO for either team (table not recomputed).

## Testing

- The test gate is on. `game_model_line`, the repository query, the router
  helper, and `nflGameModelSummary` get focused tests.
- The page itself rides on build plus screenshots (desktop and 390px).
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`; `npm run
  build` and `npm run test` from `web/`.

## Notes for the AI

- **Two spread conventions meet here.** NFLverse `spread_line` and
  `elo_margin` are the expected home margin (positive = home favored). The
  Odds API `nfl_game_odds.line`, and so `odds.homeSpread`, is the book price
  (negative = home favored): `2026_03_PHI_CHI` stores NFLverse +1.5 and
  books -1.5. The model spread must be `-elo_margin` so both numbers on the
  strip share the book sign.
- The market win probability comes from the same book as the displayed
  moneyline, not from `get_slate_market_probabilities` (any book), so the
  strip compares like with like.
- Totals: `replay` over `get_elo_games` (about 4,000 rows) on each slate
  request is cheap next to the existing slate queries, and the slate is
  cached 5 minutes on the client. Revisit only if `/nfl/slate` slows visibly.
- `nfl_team_elo` holds `elo_pre` for future weeks too, as of the latest final
  game; that is the right pre-game value for any unplayed week. It is only
  current after the Tuesday cron recomputes ELO following the stats load, so a
  slate viewed between a game's final score and that run shows ratings one
  week stale. That is acceptable for display-only context; do not add a
  per-request ELO replay to hide it.
- The API returns unrounded floats; the web helper does all rounding.
- Keep the router thin: the math lives in `core/`, SQL in the repository.
- Never color the gap green or red, never sort by it, and never add it to a
  signal board.
