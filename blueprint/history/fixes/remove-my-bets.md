# Remove the My Bets page and API

**Type:** Fix

## The problem

The owner decided on 2026-10-15 to remove My Bets. Bets are tracked in Pikkit
(open question 42), the `bets` table has no user id, so it could not carry over
to a multi-user app without a rebuild, and `/bets` is the last public route
group that writes data now that the API is being hardened for a read-only demo.

## The fix

**Remove:**

| Area | What goes |
|---|---|
| Web page | `web/src/pages/BetsPage.tsx` |
| Web data layer | `web/src/hooks/useBets.ts`; the "My Bets" block in `web/src/api/tennis.ts` (`fetchBets`, the summary fetch, `createBet`, `settleBet`, `deleteBet`) and their type imports; the "My Bets" block in `web/src/types/tennis.ts` (`BetStatus`, `BetType`, `Bet`, `DailySummary`, `BetsListResponse`, `BetCreateRequest`, `BetSettleRequest`) |
| Web nav and route | the `/bets` entry in `web/src/utils/sportNav.ts`, its three lines in `sportNav.test.ts`, the import and `<Route>` in `web/src/App.tsx` |
| Parlays "Track" buttons | `trackPick` / `trackParlay` and their `+ TRACK` buttons in `web/src/pages/ParlaysPage.tsx` (three places), which navigate to `/bets` with a prefill. The page itself stays (hidden route). |
| API | `app/routers/bets.py`, `app/repositories/bets.py`, `app/schemas/bets.py`, the router import and `include_router` in `app/main.py` |
| API tests | `tests/test_bets_schema.py` |

**Rework, not remove:**
- **`tests/test_write_route_guard.py`** keeps guarding the admin routes. Drop
  the three `/bets` writes and `test_reading_bets_needs_no_key`; re-point
  `test_the_right_key_reaches_the_route` and
  `test_writes_stay_open_when_no_key_is_configured` at an admin route, stubbing
  its repository call instead of `bets_repo`.
- **Wording:** "admin and bets routes" in the `app/security.py` warning and the
  `api/.env.example` comment become "admin routes".

**Keep:**
- **The `bets` table and migrations `0005` and `0011`.** Dropping the table
  deletes stored rows; that is a later migration once the owner has exported
  or given up the data. Migrations are never edited.
- **`/bets` in the browser** redirects to `/`, as the retired `/props` and
  `/live-odds` do.
- **Unrelated "bet" names:** "Best Bets" UI, `bettable_criteria`,
  `GET /tennis/props/bet` (Bet365 props), the bankroll builder's `bet_type`.

**Must not break:**
- every other nav entry and route, including the hidden `/parlays` page
- the admin key guard (401 without the key, open on localhost with no key set)

## Build steps

- [x] **1. Remove the web page.** Delete the page, hook, API functions and
  types, the nav entry and route, and the Parlays Track buttons; add the
  `/bets` redirect.
  - **Done when:** `grep -rn "/bets\|BetsPage\|useBets\|fetchBets\|createBet" web/src`
    finds only the redirect.
  - **Done when:** `npm run build` and `npm run test` pass.
- [x] **2. Remove the API.** Delete the router, repository and schemas, unmount
  the router, delete the schema test, rework the route guard test, and fix the
  two wording lines.
  - **Done when:** `grep -rn "bets_repo\|schemas.bets\|routers import.*bets\|/bets" api/app api/tests`
    finds nothing.
  - **Done when:** `pytest` passes, including `test_write_route_guard.py`.

## Verify

- Both suites and the web build pass.
- **Manual:** with the dev servers running:
  - the nav has no My Bets, and `#/bets` lands on the tennis slate
  - `#/parlays` still renders, with no Track buttons
  - `curl localhost:8000/bets/summary` returns 404
  - an admin write without the key still returns 401 when `ADMIN_API_KEY` is set

## Follow-ups (not in this fix)

- **Plans:** build-plan item 11 (bet tracking), `project-plan.md` §1 ("records
  placed bets and settles them") and the `/bets` rows in the generated overview
  still describe the feature. Record the removal in the plans and run
  `/overview`; this resolves open question 42.
- **Interview guide:** line 15 of `docs/SportApp-Employer-Interview-Guide.md`
  says the app "tracks placed bets and results". Update it at `/complete`
  (AGENTS.md maintenance rule).
- **Table:** drop `bets` in a later migration after exporting any rows worth
  keeping.

## Outcome (2026-10-15)

- **Checks:**
  - `npm run build` succeeded.
  - `npm run test` passed 43 files and 511 tests.
  - `pytest` gave 2550 passed (from 2570: `test_bets_schema.py` and the
    `/bets` cases in the route guard test went with the code).
- **Added beyond the spec:**
  - `test_the_bets_routes_are_gone` asserts `/bets/summary` returns 404.
  - The route guard tests now exercise `POST /admin/players/1/set-elo` with
    the player lookup stubbed.
  - Single-pick rows on `/parlays` dropped the 60px button column, so they
    line up with the header grid again.
- **Left alone:** the `bets` table and its migrations, and the comment in the
  untracked local `api/app/.env`.
- **Interview guide:** the overview paragraph now says the app grades its own
  predictions against results instead of tracking placed bets, and the
  PostgreSQL row names predictions instead of bets.
- **Follow-ups:**
  - Record the removal in build-plan item 11 and `project-plan.md` §1, then
    run `/overview` (resolves open question 42; the overview still lists
    `/bets` routes).
  - Drop the `bets` table in a later migration after exporting any rows.
