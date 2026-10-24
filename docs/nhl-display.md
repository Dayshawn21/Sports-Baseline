# NHL stored-data display

Feature 45e adds an NHL slate and game page using stored schedule, odds and
PrizePicks observations. The pages are implemented and verified locally;
deployment and GitHub workflow acceptance have not been verified in this work.
There are no NHL projections, edges, picks, grading or player-detail routes.

Feature 45f extends both pages with stored ESPN injuries and starting goalies;
see [NHL context](nhl-context.md) for source, temporal and operating rules.
Its UI/API are verified locally with controlled snapshots. Migration 0050,
real snapshot write/read acceptance, Actions and deployment remain pending.
Nonempty slate/game reads now require the migration and return an explicit
503 when context tables are absent. Empty context tables after migration
produce Unavailable, never an empty successful report.

## Routes and local review

The SPA uses hash routes:

- `/#/nhl?date=2026-10-23`: dated slate, team/game search and game links.
- `/#/nhl/game/57029`: matchup and Player Props tabs; Player Props opens first.
- `/#/how-it-works`: NHL coverage and limitations alongside the other sports.

Run the API and web dev commands in `AGENTS.md`. The usual web origin is
`http://localhost:3001`; the unset web API base uses `/api` through Vite's
proxy to `http://127.0.0.1:8000`. For an isolated API, `VITE_API_URL` overrides
that dev proxy target. `VITE_API_BASE_URL` instead sets the web client's direct
HTTP(S) API origin at build/start time. Existing stored data needs no ingest
to display; NHL context additionally requires migration 0050 as above.

| Public read endpoint | Response |
|---|---|
| `GET /nhl/slate?date=YYYY-MM-DD` | Selected date, nearest previous/next served date, games and markets |
| `GET /nhl/games/{game_id}` | Same game fields as the slate, plus line history |
| `GET /nhl/games/{game_id}/line-only-props` | Game ID and eligible stored offerings |

For example, `curl.exe http://127.0.0.1:8000/nhl/slate?date=2026-10-23`.
Responses use camelCase fields and aware timestamps. Missing, wrong-sport or
preseason game IDs return 404; invalid IDs/dates return 422. Valid empty
collections return 200. Malformed browser dates fall back to default selection;
invalid browser game IDs do not issue a game request.

## Date, identity and market contracts

Only NHL REG/PST games are served. Dates follow stored Eastern schedule dates;
displayed puck-drop and fetch times use Central time. Explicit dates remain
selected even when empty. Without a date, selection uses Eastern today if
served, otherwise the next served date, otherwise the latest served date;
an entirely empty schedule defaults to today. Adjacent controls skip dates
without served games. Missing start times remain TBD.

Every shared-table read is scoped to NHL. Odds additionally require
`provider='odds_api_io'` and exactly `draftkings` or `bet365`. For each game and
market, DraftKings is preferred when eligible observations exist, otherwise
Bet365. Latest price, opening/current movement and chart history use that same
book. Markets can have different books; neither sides nor history splice books.
Latest selection breaks timestamp ties by row ID.

For known starts, observations must be strictly before puck drop. Unknown
starts allow the latest stored prices and props, but no pre-start line history
or movement claim. Puck lines use the home team's signed line. Moneyline, puck
line and total are full-game markets including overtime and shootouts; official
final scores retain the shootout winner's goal. Book win probabilities remove
that book's margin and are reference information, not model confidence.
See [NHL game odds](nhl-odds.md) for the ingestion contract.

Props require PrizePicks, full-game segment, linked NHL player/game, a supported
market and a non-null provider offering ID. The latest eligible observation is
selected per game/provider/offering ID, with timestamp then ID ordering.
Alternate offerings remain distinct, including Standard, Goblin and Demon.
The slate count and detail rows share this predicate. Displayed team comes
from the offering's provider payload only when it matches a game side; it is
not replaced with a player's current roster team.

The twelve markets are Points, Goals, Assists, Shots On Goal, Goalie Saves,
Blocked Shots, Hits, Faceoffs Won, Time On Ice, Power Play Points, Goals Allowed
and Plus/Minus. Time On Ice lines stay in provider minutes; box scores store
seconds. No conversion to a projected result is performed. All offerings use
neutral gray styling, with no recommendation sorting or player evidence links.

## Freshness, coverage and request cost

These are stored snapshots, not live scores or live odds. Schedule/box-score
refreshes follow the ingestion schedule. Each market and offering retains its
own fetch timestamp; missing prices, history, scores or props remain explicit.
Five-minute browser query freshness does not promise five-minute source data.
Partial markets and source outages never trigger another provider or sport.

Reads use batched database queries over selected games and stored histories.
They do not invoke provider APIs, ingest, model inference, statistical history
reports, scoring or database writes. The 512 MB production API must continue
to keep heavy reports off request paths. Local response sizes and timings
below establish bounded observed reads; they do not measure production peak
memory, concurrent load or every future history size.

## Local acceptance evidence

Verified on October 23, 2026 Central time (final API sample at
`2026-10-24T03:12:15Z`) through sessions enforcing PostgreSQL read-only
transactions and a 10-second statement timeout. No provider calls or writes
were made. The ignored `output/45e-step6-http.json` records individual requests.

| Stored date | Games | Eligible offers | Displayed market coverage |
|---|---:|---:|---|
| 2026-10-23 | 2 | 495 | All three markets for both games, DraftKings |
| 2026-10-24 | 12 | 1,721 | All three markets for all games, DraftKings |

The selected odds were fetched October 23 around 23:59 UTC, approximately
3 hours 13 minutes before this verification. Selection of DraftKings does not
establish Bet365 coverage; fallback is separately tested with fixed fixtures.
Game 57029 returned 324 offerings (35 Standard, 38 Goblin, 251 Demon); game
57040 returned 221. Each count matched the slate and detail fields agreed.
Sample prop timestamps were strictly before the respective starts.

| Read | Bytes | Local elapsed time |
|---|---:|---:|
| October 23 slate | 2,169 | 576 ms |
| October 24 slate | 12,610 | 493 ms |
| Game 57029 detail | 1,259 | 424 ms |
| Game 57029 props | 72,270 | 379 ms |
| Game 57040 detail | 1,270 | 438 ms |
| Game 57040 props | 49,119 | 353 ms |

Real stored historical game 60898 showed its final score with empty markets
and props. Date 1900-01-01 stayed selected and empty. Absent and wrong-sport
IDs returned 404; malformed date/ID requests returned 422. These observations
do not establish complete historical or future provider coverage.

Desktop (1440x1000) and phone (390x844) evidence covers slate, game, props,
movement, dates, direct refresh, search by team/code/accent-free names,
keyboard activation, navigation and no horizontal overflow. Fixed browser
fixtures separately cover loading, errors/retry, null starts, shootout finals,
zero scores, partial markets and empty histories. Earlier evidence inventories
are `output/45e-step4-browser-evidence.json` and
`output/45e-step5-browser-evidence.json`; screenshots share `45e-nhl-` names.
Deliberate fixture failures are distinguished from clean live checks.

The final live pass repeated desktop/phone slate and phone props checks with
no console errors, failed responses, page exceptions or horizontal overflow.
Screenshots are `output/45e-final-slate-desktop.png`,
`output/45e-final-slate-phone.png` and `output/45e-final-props-phone.png`.
The exact root Verify command passed with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
Typecheck, 878 web tests, production build and 4,173 API tests passed.
Existing Vite chunk-size and Starlette/AnyIO deprecation warnings remain;
`git diff --check` passed. No deployment or workflow-run acceptance was tested.

To review manually, open the dated slate, search for Montreal or Tampa, open a
game, switch tabs, inspect source timestamps and Time On Ice units, then repeat
at phone width. Try an empty date and historical game as above. NHL navigation
offers only Slate; existing tennis, NFL and NBA routes remain available.
