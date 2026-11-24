# Digest cards share the tennis layout

**Type:** Fix

**Completed:** 2026-10-23

**Branch:** `fix/digest-card-layout`

## The problem

The owner found the NFL and NBA "Largest gaps" cards (38b, 38c2) laid out
differently from the tennis "Best picks · priced" cards (38c1), and preferred
the tennis layout. Tennis reads: pick, market and matchup, tournament and
time, a large price row with EV on the right, then tier and tour pills. NFL
and NBA read: player, market and matchup, a small "line / model" row, and the
gap as a muted footnote, with no start time.

## The fix

- **One shared body:** new `GapDigestBody`
  (`web/src/components/shared/GapDigestBody.tsx`), used by `NflSlateDigest`
  and `NbaSlateDigest` for both link and drawer-button cards:
  - player
  - market · matchup
  - Central start time
  - `line → model` in the large mono row, with `<gap> gap` on the right
    where tennis shows EV
  - a neutral outlined pill, `Line → model` (`Line → reference` for Rec
    Targets)
- **Styles** in `slate-digest.css`: `__arrow`, `__foot`, `__tag`; `__gap` now
  sits in the number row in secondary gray.
- **Start time:**
  - NFL: `NflSlateDigestItem.when` from the board line's `startUtc`, in the
    slate's `DAY_CLOCK` format ("Sun 3:25 PM CT").
  - NBA: `NbaSlateDigestItem.when` from `tipLabel`. `/nba/slate/gaps` items
    gain `startUtc` (`NbaSlateGapSchema.start_utc`, always set because the
    rule keeps only games not yet tipped). The client-side `nbaGameGaps`
    carries the game's `startUtc`.

**Must not break:**
- Gray signal: no green, red, over/under or tier pill on a gap card.
- Digest order, limits, labels, links and drawer opening unchanged.
- No model, version, ranking or projection change. The one API change is an
  added response field.
- 11px floor.

## Build steps

- [x] **1. Shared gap card body.** Done when NFL and NBA cards show the
  tennis structure, gray only, and web Verify passes.
- [x] **2. Start times.** Done when every card shows a CT kickoff or tip
  time, `/nba/slate/gaps` returns `startUtc`, and tests pin the new fields.

## Completion evidence

- **Verify:** `npm --prefix web run verify` (57 files, 817 tests, typecheck,
  build) and `api/.venv/Scripts/python.exe -m pytest` (3,945 passed).
- **Tests:** `nflSlate.test.ts` pins `when: 'Sun 3:25 PM CT'`;
  `nbaSlate.test.ts` pins `when: 'Tue 7:00 PM CT'` and `nbaGameGaps`'
  `startUtc`; `test_nba_slate_gaps_service.py` pins `start_utc`.
- **Browser, 1600 px, local dev against the shared database:**
  - `/nfl` week 7: four cards (Willis, Mahomes, Cousins, Watson) with Sunday
    CT kickoffs, gaps gray.
  - `/nba` 2026-10-23: four cards (Ayton, Flagg, Duren, Sexton) with Friday CT
    tips; `GET /nba/slate/gaps?date=2026-10-23` returned `startUtc`.
- **Found while checking:** spreading the NBA item into `GapDigestBody`
  passed its `key` field into JSX (React console error). Props are now passed
  explicitly; a fresh page load has no console errors.
- **Not verified:** phone width, the game-page Player Props strips, hosted
  deployment.
