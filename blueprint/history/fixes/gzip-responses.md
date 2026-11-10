# Gzip API responses

**Type:** Fix
**Completed:** 2026-11-09
**Branch:** `fix/gzip-responses`

## The problem

The API sends every response uncompressed. A local load test on 2026-11-09
measured the NFL slate for 2026 week 9 at 15.09 MB and the NBA prop board at
3.64 MB per request. The full page mix pushed 68 MB/s at 50 simultaneous users,
so Render bandwidth and phone download time give out long before the server
does.

## The fix

- Add Starlette's `GZipMiddleware` in `api/app/main.py`, outermost, so every
  JSON response is compressed when the client sends `Accept-Encoding: gzip`.
  Browsers already do, and axios needs no change.
- `compresslevel=4`, not the default 9. Measured locally on the stored bodies:

| Body | Level 1 | Level 4 | Level 6 | Level 9 |
|---|---|---|---|---|
| NFL slate, 15.09 MB | 0.90 MB, 56 ms | 0.65 MB, 99 ms | 0.53 MB, 165 ms | 0.48 MB, 416 ms |
| NBA props, 3.64 MB | 0.18 MB, 14 ms | 0.14 MB, 24 ms | 0.13 MB, 30 ms | 0.11 MB, 58 ms |

  Render's half CPU makes each of those times slower, and level 9 would spend
  about four times level 4's CPU for 26% fewer bytes.
- Ask Lineform's `text/event-stream` is in Starlette's default exclusions, so
  streaming is not buffered.
- Bodies of 128 KiB or more are compressed in a worker thread (Starlette's
  default), so a big slate does not stall the event loop.

## Build steps

- [x] **Step 1 - add the middleware.** Plus `api/tests/test_gzip.py`: a large
  JSON response comes back gzipped only when asked for and decodes to the same
  bytes, the level stays 4, and an SSE response is never compressed. The two
  `@app.middleware("http")` layers stream every body, so GZip's `minimum_size`
  never applies and `/health` is compressed too. That costs a few bytes, so the
  option is left at its default rather than set to a value that does nothing.

## Evidence

- Verify: web build and tests green, `pytest` 6,053 passed.
- Local API: `/nfl/slate?season=2026&week=9` 15,088,094 B to 645,299 B on the
  wire, `/nba/props` 3.64 MB to 139,870 B, both `content-encoding: gzip` and
  byte-identical to the uncompressed bodies once decoded.
- Load test, full mix, 50 users, 20 s: 0 errors both times, wire traffic
  67.9 MB/s to 2.1 MB/s. NFL slate p50 rose from 120 ms to 243 ms (the
  compression). Overall rps fell from 57.6 to 41.5, but the uncompressed
  database-backed slate routes slowed in the same run even at 5 users, so most
  of that drop is Neon variance, not gzip. Not deployed; the hosted CPU
  cost is unmeasured.

## Done when

- Verify passes.
- Locally, `/nfl/slate?season=2026&week=9` and `/nba/props` come back gzipped
  and decode to the same bytes as before.
- The load test's full mix shows lower bytes per second with no new errors.

## Findings

Closed before this fix, by `0428876a` and `9cda052f` and the audit that followed; archived here because they were still in the ledger when this fix completed.

### Audit 2026-11-09 (scope: last 5 commits, d281a079~1..26e25700; lenses: all)

**Scope:** commits `d281a079` (#33), `ac73e775` (#34), `966f51d6` (#35), `ed2f8146` (58) and `26e25700` on `master`, chosen by the user over `full` (no active feature; the untracked files are notes and images, not source). The range touches only `web/` and `blueprint/`: 71 web files.
**Signals:** `npm --prefix web run verify` passed (96 test files, 1,435 tests, typecheck, build). API tests not run: no API file is in the range. No lint command exists.
**Clean:** every new pure helper has a test (`playerGameLog`, `playerProjection`, `injuryTone`, `latestTime`, the NBA, NHL, NFL and tennis hero and footer builders, `teamLogoUrl`, `matchupSegment`); new tags, projection heroes and line-type tags stay gray; the tennis side and EV cells reuse the board's 48f/48g coloring unchanged; the removed NFL lines card and game-market block were specced removals; no `any`, no new direct axios or fetch; the logo URL is built from stored team codes only.

### gzip-responses/F-43 [P3] closed - TennisPropEvidenceBody.tsx is dead after the tennis player-page move

**File:** web/src/components/tennis/TennisPropEvidenceBody.tsx:24; web/src/components/tennis/TennisPropEvidenceBody.tsx:71
**Found:** 2026-11-09 by /audit (scope: last 5 commits; lens: quality)
**Why it matters:** `966f51d6` replaced its only use in `PlayerPropTabs.tsx` with `TennisMarketPanel`. Its two exports, `TennisRecentBars` and `TennisPropEvidenceBody` (88 lines), now have no importer, and its side-cell logic is a third copy of the rule in `TennisPropTable.tsx:35` and `TennisMarketPanel.tsx`, so a later color change could update a copy nobody renders.
**Suggested fix:** delete the file. Its CSS classes stay, since `TennisMarketPanel` reuses them from `pages/tennis-prop-board.css`.
**Resolution:** Fixed 2026-11-09 on `claude/player-page-dead-code-19b957`: deleted `TennisPropEvidenceBody.tsx`; the `tennis-prop-evidence__*` classes stay in `pages/tennis-prop-board.css`. `rg` finds no reference and web verify passed (96 files, 1,435 tests). A later `/audit` closes it. Closed 2026-11-09 by /audit (scope: `0428876a` and `9cda052f`; lenses: all): the file is gone on `master` and `rg` finds no reference to `TennisPropEvidenceBody` or `TennisRecentBars` in `web/src`. Its side-cell rule now lives only in `TennisPropTable.tsx` and `TennisMarketPanel.tsx`. The same commit lowered the shared lines-table cell colors into `:where()` (`player-panel.css:221`, `:239`, `:254`), so the tennis side, EV and margin classes win on every row; no other stylesheet targets `.nfl-prop-detail__table`, no bare `td` or `small` rule exists, and the browser check showed the selected tennis row with primary type and line cells and a muted side cell. No new defect.

### gzip-responses/F-44 [P3] closed - Orphaned game-market CSS left in nfl-prop-detail.css

**File:** web/src/components/nfl/nfl-prop-detail.css:138; web/src/components/nfl/nfl-prop-detail.css:152
**Found:** 2026-11-09 by /audit (scope: last 5 commits; lens: quality)
**Why it matters:** `.nfl-prop-detail__model` styled the `DetailGameMarket` block that `ac73e775` removed. No `.tsx` or `.ts` file uses the class now. It was the only orphan found in the 11 stylesheets the range changed.
**Suggested fix:** remove both `.nfl-prop-detail__model` rules.
**Resolution:** Fixed 2026-11-09 on `claude/player-page-dead-code-19b957`: removed both `.nfl-prop-detail__model` rules; `.nfl-prop-detail__kv` and the other rules are unchanged. `rg` finds no reference and web verify passed. A later `/audit` closes it. Closed 2026-11-09 by /audit (scope: `0428876a` and `9cda052f`; lenses: all): both `.nfl-prop-detail__model` rules are gone and `rg` finds the class nowhere in `web/src`; `.nfl-prop-detail__kv` and the neighbouring rules are intact. No new defect.

### gzip-responses/F-45 [P3] closed - Team logos download 500px PNGs for 14 to 52px slots

**File:** web/src/utils/teamLogo.ts:19; web/src/components/shared/TeamLogo.tsx:15; web/src/components/shared/SlateMatchupTeams.tsx:7; web/src/components/home/HomeSportCard.tsx:7
**Found:** 2026-11-09 by /audit (scope: last 5 commits; lens: performance)
**Why it matters:** every logo uses ESPN's `/500/` file, displayed at 16px in slate rows, 14px on home cards and 52px in game heroes. `loading="lazy"` limits this to visible rows but does not shrink each file.
**Measured 2026-11-09** (user approved the CDN requests): the NBA slate for Mon Nov 9 (8 games, local dev server in Playwright Chromium at 1028px wide) rendered 16 logos at 16x16, all 16 loaded, each 500x500 natural size. The NHL slate rendered 6 at 16x16; the home page rendered none that night (home logos only appear in a card's "next" line, at most 2 per sport card). Resource Timing reports 0 bytes for these files because ESPN sends no `Timing-Allow-Origin`, so the byte counts come from fetching the same 16 URLs with `curl`:

| Variant for the 16 NBA logos | Total bytes | Per logo |
|---|---|---|
| `/i/teamlogos/nba/500/{code}.png` (current) | 978,608 | 22.7 to 95.6 KB |
| `/i/teamlogos/nba/500/scoreboard/{code}.png` | 978,608 | identical bytes, no saving |
| `/combiner/i?img=/i/teamlogos/nba/500/{code}.png&w=40&h=40` | 31,876 | 1.3 to 2.9 KB |
| same combiner at `w=104&h=104` (52px hero at 2x) | 107,205 | 3.8 to 9.5 KB |

PNGs are not gzipped, so transfer roughly equals these totals on a cold cache. The current files cost about 31 times the bytes of a 40px (2x of 16px) combiner image, and each decodes to about 1 MB of RGBA (500x500x4), so 16 MB of decoded bitmaps for one NBA slate against about 100 KB at 40px. The combiner returns a 40x40 RGBA PNG with `Access-Control-Allow-Origin: *` and works for NHL too (`nhl/500/tor.png`: 56,235 bytes vs 1,918 at 40px).
**Suggested fix:** in `teamLogoUrl`, take the display size and return the combiner URL `https://a.espncdn.com/combiner/i?img=/i/teamlogos/{sport}/500/{code}.png&w={2*size}&h={2*size}` for row-sized slots (16px slate rows, 14px home cards), keeping the plain `/500/` file for the 52px game heroes, and keep the existing `onError` fallback to the code badge (or nothing) unchanged, so a combiner failure still degrades cleanly. Add a `teamLogo.test.ts` case for each branch (row size gives the combiner with doubled dimensions, hero size gives `/500/`, NHL overrides still apply). Optional: the 104px combiner would cut a hero from about 61 KB to about 6.7 KB, but the audit asked to keep heroes on the 500px file.
**Resolution:** Fixed 2026-11-09 on `fix/team-logo-size`: `teamLogoUrl(sport, code, size)` returns ESPN's combiner URL at twice the display size for every slot (user chose heroes too), and `TeamLogo` passes its size. Tests cover 16, 14 and 52px, rounding, the NHL overrides and blank codes; web verify passed (1,447 tests). The NBA slate's 16 logos and the NHL slate's 6 load at 32x32, an NBA hero at 104x104. A later `/audit` closes it. Closed 2026-11-09 by /audit (scope: `0428876a` and `9cda052f`; lenses: all): `teamLogoUrl` (`web/src/utils/teamLogo.ts:19`) is the only place that builds an ESPN logo URL, every `TeamLogo` caller (slate rows 16px, home cards 14px, heroes 52px) now gets the combiner at twice its size, `TeamLogo` keeps its display `width`/`height` and `onError` fallback keyed on the new URL, and the tests cover each size, rounding, the NHL overrides and blank codes. Full Verify passed on this code (web 1,447 tests and build, API 6,043). Remaining unverified, not a defect: the blocked-CDN fallback and the live Render site were not checked.

### Audit 2026-11-09 (scope: `0428876a` and `9cda052f`; lenses: all)

**Scope:** the two fix commits for F-43 to F-45, chosen to close them (no active feature, no local source changes): `nfl-prop-detail.css`, `player-panel.css`, the deleted `TennisPropEvidenceBody.tsx`, `teamLogo.ts`, `TeamLogo.tsx` and `teamLogo.test.ts`, plus their callers.
**Signals:** full Verify passed this session on `9cda052f`'s code: `npm --prefix web run verify` (96 files, 1,447 tests, typecheck, build) and `python -m pytest` (6,043 passed). `rg` finds no reference to the removed component or class. Browser evidence from earlier this session: the tennis lines table keeps gray side and EV cells with a brighter selected row; NBA and NHL slate logos load at 32x32 and an NBA hero at 104x104.
**Ledger:** closed F-43, F-44 and F-45. No new finding.
