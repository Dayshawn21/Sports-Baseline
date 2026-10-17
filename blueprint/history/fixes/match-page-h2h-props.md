# Fix: Match page H2H meetings and expandable props

**Type:** Fix
**Status:** complete (2026-09-29)
**Branch:** `fix/match-page-h2h-props`

## The problem

Two cards in the match page sidebar (32a,
`web/src/components/tennis/match/MatchSidebar.tsx`) stop short:

- **Head to head** shows only win counts ("1 - 0", "Hard 1 - 0"). It does not
  say when or where the players met, or the score.
- **Props on this match** shows 8 lines, then links away to the prop board
  ("All 15 lines on the prop board"), which drops the reader on an unfiltered
  board instead of showing the rest of this match's lines.

## The fix

**Meetings in the H2H card.** Under the counts, list each past meeting,
newest first: date, tournament and round, surface, score, and the winner.

- Source: completed rows in `matches` between the two players, before this
  match's date, oriented so the score reads from the winner's side as stored.
- **The counts and the list can differ.** The counts come from
  livetennisapi's all-time `/h2h`; stored matches start 2023-01-01. On
  2026-09-29, 80% of counted meetings (5,245 of 6,578) are stored and 2,857
  of 3,893 pairs are fully covered. When fewer meetings are listed than
  counted, the card says so ("3 of 5 meetings shown · stored since 2023"),
  never implying the list is complete.
- Extends `MatchDetailResponse` (load-bearing, 32a) with `meetings`, rather
  than adding an endpoint. No schema change, no provider call.

**Props expand in place.** Show the first 8 as today; a "Show all 15 lines"
button expands the card to every line for this match, and "Show fewer"
collapses it. No pagination, no navigation. Each line still links to the prop
board.

Must not break: the H2H counts, the prop sort order (standard lines first, then
tier), and the page's other sections. Display only; no probability or pick
changes.

## Build steps

- [x] **Step 1 - Meetings in the API** - repository `get_meetings(db, p1_id,
  p2_id, before)` returning completed matches between the two players dated
  before `before`, newest first: date, tournament, round, surface, score,
  winner id. `build_match_detail` adds them; `MatchDetailResponse` gains
  `meetings: list[MatchMeeting]` with `winner_side: "p1" | "p2" | null`
  oriented to this match's p1/p2 (the stored match may list the players the
  other way round). *Done when:* pytest covers the orientation both ways, a
  missing winner, and the date cap, and `GET /tennis/matches/{id}` for a
  Lehecka-Bergs match returns the Doha R16 2026-02-18 meeting, 6-2 6-1, won by
  Lehecka.
- [x] **Step 2 - Meetings in the H2H card, props expand** - the H2H card lists
  meetings under the counts (date, tournament and round, surface, score, the
  winner's name); a "N of M meetings shown · stored since 2023" note when the
  list is shorter than the count; the existing empty state when they have
  never met. The props card gets a Show all / Show fewer toggle in place of the
  link. *Done when:* `npm run build` and `npm run test` pass, and screenshots
  at 1440px and 390px show a pair with one meeting, a pair whose count exceeds
  its stored meetings, and the props card collapsed and expanded.

## Verify

1. Open a match page for two players who have met (for example Lehecka v
   Bergs): the H2H card lists Doha R16, Feb 18 2026, hard, 6-2 6-1, Lehecka.
2. Open a long rivalry older than 2023: the card lists what is stored and says
   how many of the counted meetings that is.
3. On a match with more than 8 prop lines, "Show all" expands the card in
   place and "Show fewer" collapses it; the URL does not change.

## Notes for the AI

- SQL in `app/repositories/matches.py`; orientation logic is a pure function
  with a test. Reuse `winner_side`'s approach, not a new convention.
- Cap at `match_date < this match's date` so a finished match never lists
  itself.
- Keep `.tennis-match-table` styling; no new colors.
