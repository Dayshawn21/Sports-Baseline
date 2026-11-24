# Feature: Home page

**From build-plan:** feature 55
**Status:** complete (2026-11-03)
**Branch:** `feature/home-page` (worktree `.claude/worktrees/55-home-page`)
**Dependencies:** completed sport shell (54a-54c: `sportNav.ts` registry, per-sport slate, props and model pages)

## Goal

`/` stops being the tennis slate and becomes a one-screen cross-sport home.
The sport with the nearest upcoming games leads: its slate counts, its largest
gaps (gray reference) and links to its Slate, Props and Model. The other sports
shrink to an "Also today" strip ordered by first start time. Each sport's
published model record is linked, reading "Accruing" where no rule has adopted.
The tennis slate moves to `/tennis`.

Built only from data the existing slate, gap and record hooks already load. No
new endpoint, no model or rule change; gray stays gray. Bets were retired on
2026-10-15, so nothing here reads bets.

## Design reference

- [`prototypes/home.html`](../../prototypes/home.html) - prototype C. Open it
  beside the build. Every name, number and count in it is a placeholder.
- It has no `theme.css`; the app's tokens in `web/src/index.css` are the source
  of truth (`--bg-card`, `--border-card`, `--text-secondary`, `--positive`, the
  Barlow Condensed / DM Sans / JetBrains Mono fonts, `--radius`). Use those, do
  not copy the prototype's `:root`.
- Phone layout is in the file (`max-width: 640px` and `900px` queries): the hero
  stacks, the gaps table drops its Market column, strip rows stack.
- **Deviations from the prototype, for the owner to confirm at this gate:**
  1. The shell gets a **Home** entry (the prototype's first tab) and the
     wordmark links to `/`.
  2. A compact **Model records** section sits under the strip (Decision 6),
     since the prototype only shows the lead sport's record.
  3. The prototype's "Open the slate / Prop board / Model" buttons are omitted
     for a sport without that view (NHL has only a slate).

## Decisions fixed here (change them at review, not mid-build)

1. **Which sport leads.** Per sport, take the earliest start strictly after now
   among its games (NFL current week, NBA and NHL today's slate, tennis matches
   with a stored price). The sport with the earliest such start leads. Starts
   within 3 hours of the earliest count as tied, and a tie goes to a team sport
   (NFL, NBA, NHL in that order) before tennis, because tennis plays around the
   clock and would otherwise lead every day. A sport with no upcoming start
   cannot lead. This is a pure function with a fixed `now`.
2. **No lead.** If no sport has an upcoming start, the page has no hero: a
   quiet "Nothing scheduled" panel, then the same strip and records.
3. **Hero content by lead sport.**
   - NFL: week and season, next kickoff, game count, prop line count, up to 3
     largest gaps (from `slateDigest(buildNflPropBoard(...))`), links to
     `/nfl`, `/nfl/board`, `/nfl/model`.
   - NBA: same shape, gaps from `useNbaSlateGaps`, links to `/nba`,
     `/nba/board`, `/nba/model`.
   - NHL: counts and the next 3 games; no gaps (props are line-only, no NHL
     picks), links to Slate only.
   - Tennis: priced match count and the next 3 priced matches, with links to
     `/tennis`, `/tennis/board`, `/tennis/model`. No prop count and no picks: the
     home reads only `useTennisToday`, and never re-ranks or re-colors anything.
4. **Gaps are gray.** NFL and NBA gap values use `--text-secondary`, with the
   note "Gray reference, not picks." until a slice adopts. No green, no pick
   wording.
5. **Empty and failure states** (each sport is independent; one failing never
   blocks the page):
   - NHL with no games: strip row reads "No games today", quiet (65% opacity
     like the prototype's `.s.q`).
   - Tennis with no priced matches: "No priced matches", quiet (the tennis
     feed only holds priced matches, so there is no later start to name).
   - NFL or NBA with no games in range: "No games scheduled", quiet.
   - A sport whose query errors: "Could not load" with a retry link in its
     strip row; the hero is skipped if the lead's data errors and the next
     eligible sport leads. If every sport errors, show `ErrorState`.
   - Loading: `LoadingState` only while no sport has any data yet; afterwards
     each row fills in as its query returns.
6. **Model records.** A "Model records" section lists Tennis, NFL and NBA, each
   linking to its `/model` page with a label from the existing record data:
   the adopted-slice count when one exists, otherwise **Accruing**. NHL has no
   model page and gets no record row. The lead sport's record also appears as
   a hero stat. No record is computed on the home; labels come from the
   existing summary helpers (`nflTrackRecord`, `nbaModel`) and the tennis
   record hook already used by `TennisModelPage`.
7. **Strip order** is by first upcoming start (earliest first); sports with no
   upcoming start sort last, in registry order. The lead is excluded from the
   strip.
8. **Shell.** Add Home to the top bar and the phone drawer; `/` highlights Home
   and no sport tab. Title for `/` is the bare app name. The tennis tab and
   slate path become `/tennis`. Detail pages under `/tennis/` are unchanged.
9. **Redirects.** `/props`, `/live-odds` and `/bets` keep redirecting to `/`
   (now the home).
10. **Data cost.** The home loads the same queries the sport pages use, with
    the same query keys and 5 minute `staleTime`, so opening a slate after the
    home is a cache hit. It reads the slates only, never a game or player
    detail.

## Scope

- **In:** `/` route and `HomePage`; moving the tennis slate to `/tennis`
  (registry, crumbs, titles, tests); Home in the shell; pure home helpers and a
  composing hook over existing hooks; hero, strip and records components;
  empty, loading and error states; phone layout.
- **Out:** any new endpoint, API or migration; model, rule, version or
  threshold changes; ranking, picking or recoloring anything; bets, parlays;
  personalization or settings; notifications; a new date picker (the home is
  always "today"); deploy.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step, then implement only that step on the feature branch.
2. Show the diff and prove the done-when with evidence.
3. Run the documented Verify gate; get the owner's review before moving on.
4. After approval, tick the step and offer an optional checkpoint.
   `/complete` owns the work-level commit and merge.

## Build steps

- [x] **Step 1 - Move tennis to `/tennis`, add Home to the shell (client).**
  In `web/src/utils/sportNav.ts` change the tennis slate path in `SPORTS` to
  `/tennis`; add a Home entry to `shellNav` and `menuSections` (path `/`,
  active only on `/`) and make `documentTitle('/')` the app name. Mount a
  placeholder `HomePage` (page head and links to the four slates) at `/` in
  `App.tsx`; the three redirects keep pointing at `/`. Point
  `TennisMatchPage` and `TennisPlayerPage` crumb fallbacks at `/tennis`;
  check `HowItWorks`, Ask starters and any `'/'` link for tennis assumptions.
  *Done when:* updated tests pass (`sportNav.test.ts`, `documentTitle.test.ts`,
  `sportPages.test.ts`: tennis slate `/tennis`, `/` is no sport view, Home tab
  active on `/`, drawer starts with Home, titles); in the browser `/#/tennis`
  shows the tennis slate, `/#/` shows the placeholder, `/#/props`,
  `/#/live-odds` and `/#/bets` land on `/`, and a tennis match page's back link
  returns to `/tennis`.

- [x] **Step 2 - Home rules (pure helpers, `web/src/utils/home.ts`).**
  Types and functions over plain inputs and an explicit `now`: per-sport
  `nextStart`, `chooseLead` (Decision 1 and 2), `stripOrder` (Decision 7), the
  per-sport empty-state text (Decision 5), and the hero and strip view models
  built from the existing summary and digest outputs. No fetching, no `Date.now()`.
  *Done when:* `home.test.ts` proves, on fixed timestamps: nearest start leads;
  a tennis start 2 hours earlier than an NFL start still loses the tie; one
  5 hours earlier wins; no upcoming start gives no lead; finished and
  past-start games are ignored; strip order and last-place rule; each empty
  text; an errored sport is skipped for the lead.

- [x] **Step 3 - Home data hook (client).** `useHomeData` composes the existing
  hooks (`useNflCurrentWeek`/`useNflSlate`, `useNbaSlate`/`useNbaSlateGaps`,
  `useNhlSlate`, `useTennisToday`, the NFL, NBA and tennis record hooks) with
  their existing keys, and returns per-sport `{ status, ... }` plus the
  Step 2 view models. No new endpoint or query key.
  *Done when:* the placeholder page prints the lead sport and each sport's
  status from real local data, the Network panel shows only requests the sport
  pages already make, and a forced failure of one sport (bad base URL for its
  route or a blocked request) leaves the others loaded. Tests only for any
  non-trivial pure mapping added here.

- [x] **Step 4 - Hero and strip (components, phone layout).** Components under
  `web/src/components/home/` and `home.css`: `HomeHero` (stats, gaps table with
  the gray note, links), `HomeStrip` (rows ordered per Decision 7, quiet and
  error rows), the page head (title "Today", one status line with the date and
  the lead, per the page-head convention: no eyebrow or filler subtitle).
  Tokens from `index.css`; Ant Design only where it already is.
  *Done when:* browser check at desktop and 390px width against
  `prototypes/home.html`: hero stacks, Market column hidden, strip rows stack,
  no horizontal overflow; gap values are gray; each button navigates to the
  right view; a sport with no games shows its quiet text.

- [x] **Step 5 - Model records (component).** `HomeRecords` per Decision 6,
  using the existing summary helpers; lead sport's record also in the hero stat.
  *Done when:* NFL, NBA and tennis rows link to their model pages and read
  "Accruing" (or an adopted count) matching what each model page's own summary
  shows right now; NHL has no row; a loading or failed record shows a quiet
  placeholder, not a fake value.

- [x] **Step 6 - Verify, check and documentation.** Run full Verify
  (`npm --prefix web run verify && cd api && python -m pytest`) and `/check`
  across the lead cases available in local data (NFL leading; force the others
  by test fixtures, no database writes). Record evidence in Results. Update
  the local employer guide (untracked, never staged) and the sport nav note in
  the project overview if it names `/` as the tennis slate.
  *Done when:* Verify passes, the spec's Results record each check, and
  `blueprint/context/project-overview.md` and `build-plan.md` only change where
  they named the old `/`.

## Files / areas

| Area | Files |
|---|---|
| Registry and shell | `web/src/utils/sportNav.ts` and test, `web/src/App.tsx`, `web/src/utils/documentTitle*.test.ts`, `web/src/routes/sportPages.test.ts` |
| Tennis crumbs | `web/src/pages/TennisMatchPage.tsx`, `TennisPlayerPage.tsx` |
| Home rules | `web/src/utils/home.ts`, `home.test.ts` |
| Data | `web/src/hooks/useHomeData.ts` (composes existing hooks) |
| UI | `web/src/pages/HomePage.tsx`, `web/src/components/home/*`, `home.css` |
| Docs | this spec's Results, local employer guide (untracked) |

## Data / contracts

| Contract | Required behavior |
|---|---|
| Routes | `/` home; `/tennis` tennis slate; `/tennis/board`, `/tennis/model`, `/tennis/match/:id`, `/tennis/player/:id` unchanged; `/props`, `/live-odds`, `/bets` redirect to `/` |
| Registry | `SPORTS` stays the one source of sport paths; the home reads view paths from `sportViews`, never hardcodes them |
| Lead rule | Decision 1, a pure function; the only place "in season" is defined |
| Gray | NFL and NBA gaps render gray with the reference note; the home adds no color or wording that suggests a pick |
| Record labels | derived from existing record data; "Accruing" whenever no slice has adopted |
| Backend | none; no endpoint, schema or model changes |

## Testing

Test gate on. Pure logic ships Vitest tests with fixed timestamps (`home.ts`,
the `sportNav.ts` changes, the title mapping). Components and the hook ride on
the build, the browser checks at desktop and phone widths, and network
evidence. Final gate: `npm --prefix web run verify && cd api && python -m pytest`
from the repo root with the API venv first on PATH.

## Notes for the AI

- Do not implement during `/feature`.
- This worktree's `current-feature.md` was the 49e spec carried from `master`;
  it belongs to the 49e item on its own branch and is replaced here. Expect a
  conflict on that one file at merge: keep 49e's version on `master` until
  `/complete`, and let `/complete` reset it to the stub.
- Use the app's tokens; the prototype's `:root` values are not the source.
- Comment the why only; no em dashes in new content.
- NHL is slate-only (no board, no model); do not add either link for it.
- Tennis slate fetches two UTC dates (`useTennisToday`); reuse it as is, do not
  add a date parameter.
- Windows: run Python from the API venv in the main checkout; this worktree has
  no `api/app/.env`. The web app needs only the API base URL (`VITE_API_BASE_URL`
  or the dev proxy) to show real data.

## Results

Verified 2026-11-03 in this worktree (`npm --prefix web run verify`; API `pytest` with the main checkout's venv and a dummy `DATABASE_URL`, as CI does).

- **Web:** typecheck, 79 test files and 1181 tests, build: pass.
- **API:** 5509 passed. A real regression surfaced: the Ask link builder (`api/app/core/ask_links.py`) still sent tennis slate links to `/`, and the web's Ask link whitelist (`web/src/utils/askAnswer.ts`) only accepted `/`, so the new `/tennis` link would have rendered as plain text. Both now use `/tennis`, with tests updated (`test_ask_links.py`, `askAnswer.test.ts`; `/` is now rejected as an Ask link).
- **Browser (local API, real data):** `/` leads with NHL (games tonight 6:00 PM CT; tennis starts 3:10 PM, inside the 3-hour tie, so the team sport wins); NFL forced as lead showed week 9, 15 games, 1,084 prop lines, three gray gaps and Slate, Props, Model links; no-lead state showed "Nothing scheduled" with all sports in the strip; all-sports-failed state showed "Could not load" rows. 390px width: no horizontal overflow, Market column hidden, strip and records stack. `/props`, `/live-odds`, `/bets` redirect to `/`; `/tennis` is the tennis slate.
- **Records match the model pages:** tennis "Not ahead" equals the tennis model page's headline card; NFL and NBA "Accruing" equal their API verdicts (no slice adopted).
- **Not covered:** a single sport failing while others load (unit tests only); a live day where tennis leads; the tennis match page back-link click-through.
- **Operating notes:** the home also fires the tennis, NFL and NBA model-record queries; cold they took over 10 seconds, warm 20 to 230 ms, and the page fills those rows in when they arrive. No endpoint, schema or model change.
- **Spec deviations:** tennis hero shows priced matches and the next three (no prop count or digest); quiet rows use muted text instead of 65% opacity; tennis record is the ensemble-versus-market read because tennis has no adoption rule; tennis empty text is "No priced matches" with no "until" time.
- **Docs:** local employer guide updated (untracked, not staged). Project overview row 55 and the build plan still read "not started"; `/complete` flips them.
