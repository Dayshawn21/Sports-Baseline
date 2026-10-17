# NFL PrizePicks drops Rush Yards and Anytime TD lines

**Type:** Fix
**Completed:** 2026-09-18

## The problem

`api/app/ingest/prizepicks_nfl.py` keeps a PrizePicks line only when its
`stat_type` matches a key in `MARKET_ALIASES`, and it drops every other line
without logging. Two supported markets never match because the aliases do not
use PrizePicks' current names:

| PrizePicks `stat_type` | Alias we have | Market | Full-game lines dropped (2026-09-18 board) |
|---|---|---|---|
| `Rush Yards` | `rushing yards` | `rushing_yards` | 632 |
| `Anytime TDs` | `anytime touchdowns` | `anytime_touchdown` | 414 |

As a result, `nfl_prop_lines` holds no `rushing_yards` or `anytime_touchdown`
rows, and the NFL slate shows neither market. The drop is invisible because the
ingest reports only how many lines it kept, not which stat names it skipped.

## The fix

1. Add `"rush yards"` and `"anytime tds"` to `MARKET_ALIASES`. Keep the old
   spellings so an older provider name still maps.
2. Count unmapped `stat_type` names across all fetched leagues in a run, and log
   them once at the end of the run (name and count, most common first). Put the
   counting in a small pure helper so it can be tested without HTTP.

Must not break:

- Deliberate exclusions stay excluded (`First TD`, `Longest Reception`, combos,
  defense, kicking). This fix does not add markets.
- `--dry-run` and `--relink` behavior, the rate-limit handling, and the
  per-league request pacing.
- No new provider requests. The log uses data the run already fetched.

Out of scope: `Pass TDs`, `Rush TDs`, `Rec TDs`, `Rush+Rec Yds`,
`Pass+Rush Yds`, `Rec Targets`, and `INT`. Each needs a new market and
projection, so it is a separate feature.

**Known limitation, not changed here:** for `anytime_touchdown` the baseline is a
probability, so the slate edge is `P(TD) - line` (for example `0.38 - 0.5 = -0.12`).
The direction is meaningful, but the magnitude is not comparable to yardage
edges. Rank and threshold anytime-TD edges in a later feature.

## Build steps

- [x] **Step 1 - map the provider names and log what is dropped.** In
  `prizepicks_nfl.py`, add the two aliases and a pure
  `unmapped_stat_counts(items) -> Counter[str]` helper. In `run()`, collect
  unmapped names across the leagues and log one warning line listing them.
  Extend `api/tests/test_prizepicks_nfl.py` for both spellings, `First TD`
  staying unmapped, and the helper counting only unmapped names.

## Verification evidence

- `.venv\Scripts\python.exe -m pytest`: 779 passed.
- `python -m app.ingest.prizepicks_nfl --dry-run`: 7,532 lines kept across full
  game, first half, and first quarter; the skipped-stat log no longer lists
  `Rush Yards` or `Anytime TDs`.
- After a real ingest, `GET /nfl/slate?season=2026&week=2` returned 592
  full-game `rushing_yards` and 375 full-game `anytime_touchdown` lines across 15
  of 16 games. DET @ BUF had none because it kicked off before the fixed ingest
  ran.

## Follow-ups

- Almost all Anytime TD lines are goblin or demon (5 standard across the week),
  so most show no edge. Planned next: sportsbook `player_anytime_td` odds from
  The Odds API, one market, within the free 500-credit plan.
- `project-overview.md` lists Odds-API.io for NFL and The Odds API for tennis;
  the code is the reverse (`nfl_odds.py` uses api.the-odds-api.com, tennis
  `odds_api.py` uses api.odds-api.io). Correct on the next `/overview`.
