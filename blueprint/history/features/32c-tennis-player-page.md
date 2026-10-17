# Feature: Tennis player page

**From build-plan:** feature 32c (parent: 32. Tennis detail pages)
**Status:** complete (2026-09-30)

## Goal

Give every tennis player a linkable page at `/tennis/player/:playerId`, built
after `prototypes/tennis-player.html`:
- ELO over time, overall and by surface
- 52-week serve and return by surface against the tour average
- a match log with box scores
- record splits
- the player's settled past props

The match page and the slate link to it. **Display only:** no probability,
edge, rank or pick changes, and nothing on the page takes a signal color.
32c is the last item-32 page.

## Design reference

- `prototypes/tennis-player.html` - header with next match, ELO card (big
  number, trend chart, surface row), serve and return bars against a tour
  average mark, match log table, and a sidebar (record, past props, identity).
- `prototypes/theme.css` - already ported in 31a; nothing to port.
- 32a's `tennis-match.css` and `components/tennis/match/`, and 32b's
  `tennis-model.css`, are the patterns for classes, cards and states.
- **Where the mockup and this spec differ, the spec wins:**
  - **No 3M / 6M / 1Y / All toggle on the ELO chart.** Stored ELO starts
    2026-01-05 with about 11 snapshots per player, so every range would show
    the same line. The chart shows all history, and the caption says how many
    snapshots.
  - **Serve and return labels follow the stored meaning** (open question 30):
    "BP converted", not "Break", for `break_pct`; "Ace rate" and "DF rate" are
    per serve point, not "per game". Bars scale per metric (see Data /
    contracts).
  - **Identity drops "Sources linked 4 / 4".** Only livetennisapi and
    TennisAbstract have id columns; Odds-API.io and PrizePicks do not. The
    card shows aliases, the ELO as-of date, and when rolling stats were
    computed.
  - **Grayscale throughout.** W and L, hits and misses, and the model-pick
    summary use weight and gray, never green or red. Tour tags keep their
    accents.
  - **The crumb goes to the slate** ("← Tennis slate"), as on the match page,
    not to one specific match.

## In scope

- **Backend**
  - Pure `app/core/tennis_player.py`: record splits, tour averages, and the
    ELO summary.
  - `GET /tennis/players/{player_id}` (profile, ELO history and tour rank,
    next match, identity).
  - `GET /tennis/players/{player_id}/serve-return` (four surfaces against the
    tour average).
  - `GET /tennis/players/{player_id}/matches` (match log with box scores, and
    52-week record splits).
  - `GET /tennis/players/{player_id}/props` (settled `props-v2` snapshots).
  - `p1_id` / `p2_id` on the slate's `MatchPrediction`, so the slate can link.
- **Web**
  - Types, API functions, hooks, and a pure `src/utils/tennisPlayer.ts`.
  - The `/tennis/player/:playerId` route and `TennisPlayerPage`: header, ELO
    card, serve and return, match log, and a sidebar (record, past props,
    identity).
  - Loading, error, not-found and empty states, and mobile stacking.
  - Player names link here from the match page (header and match log
    opponents) and from the slate's detail panel.

## Out of scope

- Any model, edge, rank, tier or pick change.
- Grading a player's picks as evidence. The page shows them as anecdote, and
  the model page (32b) grades the full sample.
- **Renaming the misnamed rolling-stat columns** (open question 30). That is
  item 17 or a migration; this page only labels them correctly.
- ELO ranges, a head-to-head explorer, and a player search. The page is
  reached by link only.
- Links from the prop board or the NFL pages.
- Fixing the Bet365 set-handicap parser (open question 33).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at
   the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure player core.** Add `app/core/tennis_player.py`:
  - `record_splits(matches, as_of) -> RecordSplits` over `PlayerMatchRow`
    (defined in Data / contracts). The window is the last 365 days before `as_of`. It returns:
    - all
    - per surface
    - vs top 20 (opponent rank at match time 20 or better)
    - deciding sets (a finished score going the full distance: 3 sets in
      best-of-3, 5 in best-of-5)
    - tie-break sets won and lost (7-6 and 6-7 sets, player-oriented)
  - Rule for which matches count: all splits need a winner and a non-empty
    score. Deciding sets and tie-breaks use only scores passing
    `is_completed_score`, so retirements count in the W-L but not in the set
    splits.
  - `tour_average(stats, min_matches) -> AverageStats`: the mean of each
    metric over players with at least `min_matches`, ignoring None per metric.
  - `elo_summary(history) -> EloSummary`: the latest overall and surface ELO,
    the as-of date, and the change from the first snapshot.

  *Done when:* pytest covers:
  - wins and losses by surface
  - the 365-day window edge
  - vs top 20 with a missing rank excluded
  - deciding sets in best-of-3 and best-of-5
  - tie-break sets from both orientations
  - a retirement counted in W-L but not in set splits
  - `tour_average` skipping small samples and None values
  - `elo_summary` with one snapshot and with none
- [x] **Step 2 - Player profile endpoint.** Add `GET /tennis/players/{player_id}`
  → `PlayerDetailResponse`:
  - **Profile:** id, name, tour, hand, country, birth date, and rank (from the
    player's most recent match row with a rank).
  - **ELO:** `elo_summary`, the full history oldest first, and the tour rank by
    ELO. The rank is among same-tour players with an overall ELO on the
    player's latest `as_of_date`: 1 plus the count strictly higher, so ties
    share a rank.
  - **Next match:** the player's live match if one exists, else the earliest
    scheduled match with `match_date >= today`, ordered by `start_utc` (nulls
    last) then id, or null. A live match counts even though it started.
  - **Identity:** aliases, and the latest rolling-stats `computed_at`.
  - An unknown id returns 404.
  - SQL lives in new functions in `app/repositories/players.py` and
    `matches.py`; the service is `app/services/tennis/player_detail.py`.

  *Done when:*
  - pytest covers the mapping, the 404, no ELO rows, no next match, a live
    match chosen over a later scheduled one, and tied ELO sharing a rank
  - a curl for Jakub Mensik (id 26) returns 11 ELO snapshots, hand `R`,
    country `CZE`, and a next match or null
- [x] **Step 3 - Serve and return endpoint.**
  `GET /tennis/players/{player_id}/serve-return` returns four surfaces (all,
  Hard, Clay, Grass). Each has the player's `last_52w` overall row (matches
  count, and every metric in the table below) and the tour average from
  `tour_average` over same-tour `last_52w` overall rows with at least 10
  matches on that surface. A surface the player has no row for returns
  `player: null` with the average still present. Returns 404 for an unknown
  player.

  *Done when:*
  - pytest covers a missing surface and the average skipping small samples
  - a curl for id 26 shows Hard with 43 matches, and averages within 0 to 1
    for the percentages
- [x] **Step 4 - Match log endpoint.**
  `GET /tennis/players/{player_id}/matches?limit=20` (limit 1 to 50) returns
  the player's latest completed matches, newest first, with:
  - match id, date, tournament, round, surface, best-of
  - opponent id, name and rank at the time
  - W or L, and the score oriented to the player
  - aces, double faults, BP saved / faced, and BP won / created, from the
    box score joined by `join_box_score`
  - Add `break_points_faced` and `break_points_saved` to `BoxScoreCandidate`
    (defaulted, plus the SELECT); this is additive for every existing caller.

  *Done when:*
  - pytest covers score flipping for a p2 player, a missing box score as
    nulls, and the limit bounds (422 outside 1..50)
  - the existing box-score-join and recent-form tests pass unchanged
  - a curl for id 26 returns 20 rows with box scores on the recent ones
- [x] **Step 5 - Record splits in the matches response.** The same endpoint
  adds `record`: `record_splits` over the player's matches in the 365 days
  before today, loaded separately from the capped log.

  *Done when:*
  - a route test with the service stubbed checks the camelCase shape
  - a curl for id 26 returns an "all" W-L equal to a direct count of that
    player's matches with a winner in the window
- [x] **Step 6 - Past props endpoint.** `GET /tennis/players/{player_id}/props`
  returns the player's graded `props-v2` snapshots, newest first:
  - date, stat, line, odds type, the actual value (from `resolve_actual` and
    the box-score join), recommendation, confidence, and the outcome (`hit`,
    `miss`, `push`, `pass` for no recommendation, or `awaiting`)
  - a summary: hits and misses on standard lines with a recommendation
  - `get_graded_prop_snapshots` gains an optional `player_id` filter
    (additive)

  *Done when:*
  - pytest covers each outcome and the summary counting standard lines only
  - the 26f report tests pass unchanged
  - a curl returns an empty list for a player with no snapshots (Jannik
    Sinner, id 1, on 2026-09-29) without error
  - a curl for a player with settled snapshots returns rows whose outcomes
    agree with the 26f report's grading of the same lines
- [x] **Step 7 - Player ids on slate predictions.** Add `p1_id` and `p2_id` to
  `PredictionOutput` and `MatchPrediction`, filled from the `Match` the
  predictor already holds. This is additive; the ids are not otherwise used.

  *Done when:*
  - the predictor and best-picks tests pass
  - `/tennis/predictions/today` returns `p1Id` and `p2Id` on every match
- [x] **Step 8 - Web data layer.**
  - Types in `src/types/tennis.ts`.
  - `fetchPlayerDetail`, `fetchPlayerServeReturn`, `fetchPlayerMatches` and
    `fetchPlayerProps` in `src/api/tennis.ts`.
  - The hooks in `src/hooks/useTennisPlayer.ts`, with keys
    `['tennis', 'player', id, '<section>']`, a 5-minute staleTime, and
    `retryUnlessNotFound` on the profile.
  - The pure `src/utils/tennisPlayer.ts`:
    - `parsePlayerId`
    - `ageOn(birthDate, now)`
    - `recordText(w, l)`, e.g. "38–19 · 67%", with a dash for 0–0
    - `metricBar(value, metric)`, the percent width under each metric's scale
    - `eloChart(history, box)`, points and y-axis ticks for one or more
      series

  *Done when:* Vitest covers each helper, including a birthday not yet
  reached this year, no matches, a value above its scale (clamped), and a
  single-point series. `npm run build` passes.
- [x] **Step 9 - Route, page shell and header.**
  - `TennisPlayerPage` at `/tennis/player/:playerId`: the crumb, the header
    (initials badge, name, tour tag, rank, hand, country, age), and the next
    match linking to `/tennis/match/:id`.
  - States: `LoadingState` and `ErrorState`, a not-found page for a 404 or a
    bad id, and "No upcoming match" when there is none.
  - `tennis-player.css`.

  *Done when:*
  - screenshots at 1440px and 390px for id 26
  - `/tennis/player/999999999` and `/tennis/player/abc` show not-found
  - a reload keeps the page
- [x] **Step 10 - ELO card.**
  - The big overall number, the change since the first snapshot, and the tour
    rank by ELO.
  - An inline-SVG chart: overall solid, and the surface of the player's next
    match (else Hard) dashed, grayscale.
  - The four-surface row.
  - A caption with the snapshot count and the source.
  - No ELO rows gives an empty state; one row renders as a dot.

  *Done when:* screenshots show id 26 and a player with no ELO.
- [x] **Step 11 - Serve and return card.**
  - An All / Hard / Clay / Grass toggle, defaulting to the next match's
    surface, else All.
  - Eight bars under the stored-meaning labels, each with a dashed
    tour-average mark and the value.
  - A note with the tour, surface and matches in the window.
  - A surface with no player row shows "No matches on {surface} in 52
    weeks"; under 10 matches it adds "small sample".

  *Done when:* screenshots show Hard and a thin surface (id 26 Grass, 3
  matches), and the toggle switches every bar.
- [x] **Step 12 - Match log.**
  - Columns: date, event (tournament, round, surface), a W or L chip with the
    opponent linked to their player page and their rank, the score linked to
    the match page, aces, DF, BP saved, and BP won.
  - A missing box score shows dashes; no matches gives an empty state.
  - On mobile the table scrolls inside its card.

  *Done when:* at 1440px and 390px, clicking an opponent opens their page and
  clicking a score opens the match page.
- [x] **Step 13 - Sidebar: record, past props, identity.**
  - **Record:** all, per surface, vs top 20, deciding sets, tie-breaks.
  - **Past props:** date, stat, line, actual, and pick with outcome. Hits are
    bold, misses muted, and nothing is green. The summary line and an
    anecdote note sit below.
  - **Identity:** aliases, ELO as of, and stats computed at.
  - Every card has an empty state.

  *Done when:* screenshots show id 26, and a player with no props shows the
  empty props card.
- [x] **Step 14 - Links in, and the mobile pass.**
  - Match page: the header names link to `/tennis/player/:id`.
  - Slate: the detail panel's player names link to it, using `p1Id` and
    `p2Id`. A name with no id stays plain text.
  - The page stacks at the `useIsMobile` breakpoint with no horizontal page
    scroll.

  *Done when:*
  - from the slate and from a match page, a name click lands on the player
    page
  - 0px horizontal overflow at 390px
  - `npm run build`, `npm run test` and `pytest` all pass

## Files / areas

- **API**
  - `api/app/core/tennis_player.py` (new)
  - `api/app/services/tennis/player_detail.py` (new)
  - `api/app/repositories/players.py` - ELO history, tour rank, aliases,
    same-tour rolling stats
  - `api/app/repositories/matches.py` - next match, the player match log, and
    the record window
  - `api/app/core/box_score_join.py` and
    `api/app/repositories/player_match_stats.py` - the two BP fields
  - `api/app/repositories/prop_snapshots.py` - the optional `player_id`
  - `api/app/services/tennis/predictor.py` - player ids
  - `api/app/schemas/tennis.py`, `api/app/routers/tennis.py`
  - `api/tests/test_tennis_player_core.py`, `test_player_detail.py` and
    `test_player_routes.py` (new)
- **Web**
  - `web/src/App.tsx` - the route
  - `web/src/pages/TennisPlayerPage.tsx` and
    `web/src/pages/tennis-player.css` (new)
  - `web/src/components/tennis/player/` (new) - `PlayerHeader`,
    `PlayerEloCard`, `PlayerServeReturn`, `PlayerMatchLog`, `PlayerSidebar`
  - `web/src/api/tennis.ts`, `web/src/hooks/useTennisPlayer.ts` (new),
    `web/src/types/tennis.ts`
  - `web/src/utils/tennisPlayer.ts` and `tennisPlayer.test.ts` (new)
  - `web/src/components/tennis/match/MatchHeader.tsx` and
    `web/src/components/tennis/TennisCommandCenter.tsx` - the links

## Data / contracts

No schema change and no migration. Every endpoint is a read-only GET.

**Load-bearing:** the route `/tennis/player/:playerId` and
`PlayerDetailResponse`. Later player-level features extend this response or
add a sibling endpoint under `/tennis/players/{id}/`; they do not add another
page.

```text
camelCase over the wire

GET /tennis/players/{player_id}                   PlayerDetailResponse
  player_id, name, tour: "ATP" | "WTA", hand: "R" | "L" | null,
  country: str | null, birth_date: date | null, rank: int | null
  elo: { overall, hard, clay, grass: float | null, as_of: date | null,
         change: float | null,              # latest overall minus first snapshot
         tour_rank: int | null, tour_rank_of: int | null,
         history: [{ as_of: date, overall, hard, clay, grass: float | null }] }  # oldest first
  next_match: { match_id, start_utc: datetime | null, match_date: date,
                tournament, round, surface: str | null,
                opponent_id: int, opponent_name: str } | null
  aliases: [str], stats_computed_at: datetime | null

GET /tennis/players/{player_id}/serve-return
  tour: str
  surfaces: [{ surface: "all" | "Hard" | "Clay" | "Grass",
               player: { matches: int, <metrics> } | null,
               tour_average: { players: int, <metrics> } }]
  <metrics>: hold_pct, break_pct, first_in_pct, first_won_pct,
             second_won_pct, ret_pts_won, aces_per_game, df_per_game (all float | null)

GET /tennis/players/{player_id}/matches?limit=20
  log: [{ match_id, match_date, tournament, round, surface, best_of,
          opponent_id, opponent_name, opponent_rank: int | null,
          result: "W" | "L", score: str | null,          # player-oriented
          aces, double_faults, bp_saved, bp_faced, bp_won, bp_created: int | null }]
  record: { window_start: date, all, hard, clay, grass, vs_top20,
            deciding_sets, tie_breaks: { wins: int, losses: int } }

GET /tennis/players/{player_id}/props
  projection_version: "props-v2"
  rows: [{ snapshot_date: date, stat, odds_type, line: float,
           actual: int | null, recommendation: "OVER" | "UNDER" | null,
           confidence: str | null,
           outcome: "hit" | "miss" | "push" | "pass" | "awaiting" }]
  summary: { hits: int, misses: int }            # standard lines with a recommendation
```

**Core input for record splits** (Step 1; the repository in Step 5 maps into
it):

```python
@dataclass(frozen=True)
class PlayerMatchRow:
    match_date: date
    surface: str | None        # Hard | Clay | Grass | None
    best_of: int
    won: bool
    score: str | None          # player-oriented
    opponent_rank: int | None  # at match time
```

**Stored meaning and bar scales** (per open question 30):

| Field | Label | Bar scale |
|---|---|---|
| `hold_pct` | Hold | 0 to 1 |
| `break_pct` | BP converted | 0 to 1 |
| `first_in_pct` | 1st serve in | 0 to 1 |
| `first_won_pct` | 1st serve won | 0 to 1 |
| `second_won_pct` | 2nd serve won | 0 to 1 |
| `ret_pts_won` | Return pts won | 0 to 1 |
| `aces_per_game` | Ace rate (per serve point) | 0 to 0.25 |
| `df_per_game` | DF rate (per serve point) | 0 to 0.10 |

## Testing

The test gate is on (`pytest`, `npm run test`).

| Step | Test |
|---|---|
| 1 | pytest: record splits, the window edge, rank, deciding sets, tie-breaks, retirements, tour average, ELO summary |
| 2-7 | pytest: mapping, 404s and empty cases per endpoint, one route test each with the service stubbed, and the existing box-score, 26f and predictor tests unchanged; a curl per endpoint |
| 8 | Vitest: every `tennisPlayer.ts` helper |
| 9-14 | UI: build, then screenshots at 1440px and 390px per done-when; link clicks checked in the browser |

Components are not unit-tested (coding standards). Run pytest as
`cd api && .venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- **Layering.** SQL stays in repositories, the router stays thin, core stays
  pure, and Pydantic lives only in `schemas/`. Reuse `join_box_score`,
  `get_box_score_candidates`, `is_completed_score`, `parse_sets`,
  `resolve_actual`, `_flip_score`, and the 26f `grade` path. Do not copy
  them.
- **Orientation.** `matches.score` is p1-oriented; flip it with `_flip_score`
  when the player is p2. The opponent rank is the other side's `p?_rank` on
  that match row.
- **Honest labels.** `break_pct` is BP converted, and the two "per game"
  columns are per serve point (open question 30). Use the labels 32a's fix
  already uses.
- **No signal color anywhere on this page.** The past-props summary is a
  handful of picks, and the page says so. Tour tags keep their accents.
- **Performance.** The profile, serve-return and matches calls are single
  queries per section. The tour average reads same-tour `last_52w` overall
  rows, about 7,500 rows in total. If the first request exceeds about 1 s,
  cache the averages per tour and surface for 15 minutes with
  `TimedSingleFlight`, and note the timing.
- **Prototypes stay.** 31d and 31e still use `prototypes/`, so this
  feature's `/complete` does not discard it.
- **Windows.** Launch the API as in the memory note: set the selector event
  loop before uvicorn.
- No em dashes in code comments or docs.
