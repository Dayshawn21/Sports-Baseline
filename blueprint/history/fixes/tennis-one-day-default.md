# Fix: Tennis slate opens on one day

**Type:** Fix
**Branch:** `fix/tennis-one-day-default` (cut from `master` at `3f55e1e8`)
**Status:** complete 2026-11-08

**Outcome notes:** at 9:30 PM CT on Nov 8, `/tennis` opened on Sun, Nov 8 (20 matches, two still to start) with arrows to Nov 7 and Nov 9; `?date=2026-11-09` (56 matches), Home and the props board were unchanged. The roll to tomorrow is covered by the `defaultTennisDay` tests, not seen live.

## The problem

`/tennis` with no date shows "Today and tomorrow", the last slate that doesn't
open on one dated day (NBA and NHL do; item 57). The two-day view needs its own
rules:

- Started matches are hidden only there (57d), using the 3-hour
  `UPCOMING_BUFFER_MS`, so a match stays listed for up to 3 hours after it starts.
- Previous and Next jump to yesterday and the day after tomorrow
  (`tennisDateNeighbors(null, ...)`).
- The period line counts two slates at once ("Today and tomorrow · 75 matches").

A plain calendar day would be worse: tennis runs overnight across time zones. At
8 PM CT on Nov 8, today had 7 matches left and tomorrow 40, many starting around
2 AM CT, so opening on today in the evening would show a nearly empty slate.

## The fix

With no `?date`, the slate opens on **one Central day: today until its last
match has started, then tomorrow.** The URL stays `/tennis`.

- **Load both candidate days.** `useTennisSlate` takes an optional `days` list of
  Central days and fetches the union of their stored UTC dates (today and tomorrow
  CT are three UTC dates). Each UTC date keeps its own query key, so caches are
  shared with the other tennis pages. The hook's no-argument default, used by
  Home, the props board and player props, is unchanged.
- **Pick the day.** A pure `defaultTennisDay(startTimes, now)` returns today's CT
  date if any match on today's CT date starts after `now`, else tomorrow's.
  It reads the predictions' and best picks' start times, not props.
- **Then it is an ordinary one-day slate.** The page filters to that day
  (`composeUnifiedMatches`' `date` filter) and behaves exactly as a picked date:
  - the period line reads the date ("Mon, Nov 9, 2026 · 56 matches · ...")
  - the date picker shows that day (no "Today & tomorrow" placeholder, no clear)
  - Previous and Next step one day from it
  - started matches stay listed in start order, as on NBA and NHL; the slate
    no longer uses `upcomingOnly`
  - the empty state names the day
- **`tennisDateNeighbors`** loses its two-day branch: it always steps one day.

**Must not break:** a picked `?date=` view; the props board, Home and player
pages (they keep the hook's default); search, tour tabs, digest and legend from
57d; `unifiedTennis.ts`'s `upcomingOnly` and its 3-hour buffer, which other
callers and tests still use.

**Lean digest note:** it lists only matches that have not started, so on a day
with every match started it shows nothing. That only happens on a picked past
day: the default day always has an upcoming match, or it would have rolled over.

## Build steps

- [x] **Step 1 - Day logic, tested, unused.**
  - In `web/src/utils/tennisDates.ts`: `defaultTennisDay(startTimes, now)`.
  - Tests in `tennisDates.test.ts`:
    - an upcoming match today keeps today
    - every match started rolls to tomorrow
    - no matches today rolls to tomorrow
    - a 2 AM CT match counts as tomorrow, not today
    - CT midnight and a DST change
    - null and unreadable times are ignored
  - Nothing calls it yet, so `/tennis` renders exactly as before.

  *Done when:* the new tests pass and Verify's web half passes.
- [x] **Step 2 - The slate opens on that day.**
  - `useTennisSlate` accepts `days`; the slate page loads today and tomorrow CT
    when no date is picked, picks with `defaultTennisDay`, and filters to it.
  - Period line, picker, Previous/Next, empty state and search key read the
    chosen day; `upcomingOnly` leaves the page.
  - Remove the two-day branch of `tennisDateNeighbors` and its test.

  *Done when:*
  - `/tennis` in the evening shows tomorrow's date in the period line and picker,
    with no "Today and tomorrow" text anywhere
  - with matches still to start today, `/tennis` shows today, started ones
    included, in start order
  - Previous opens the day before the shown day; Next the day after
  - `?date=` views, the props board and Home render as before
  - Verify passes

## Verify

- Open `http://localhost:3001/#/tennis` in the evening CT: the period line names
  tomorrow's date and the count matches `?date=<tomorrow>`.
- Earlier in the day (or with a fixed clock in the unit tests): it names today
  and lists started matches too.
- Click Previous and Next: each moves one day and puts `?date=` in the URL.
- Gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes

- **Display only.** No API change, no probability, pick, tier or price change.
- **Fetch cost:** the default view loads three UTC dates instead of two, per
  source (predictions and best picks), all from stored data.
- **Timezone:** days are Central (`ctDayKey`), matching the rest of the slate;
  the old default used the UTC date, which in a CT evening was already tomorrow.
