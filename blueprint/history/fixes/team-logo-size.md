# Current Feature

## Load team logos at the size they are shown

**Type:** Fix
**Fixes:** F-45
**Branch:** `fix/team-logo-size`

### The problem

Every team logo loads ESPN's full 500x500 PNG (`teamLogoUrl` in
`web/src/utils/teamLogo.ts`), whatever slot it fills: 16px in slate rows
(`SlateMatchupTeams`), 14px on home cards (`HomeSportCard`) and 52px in the NBA,
NFL and NHL game heroes.

Measured on 2026-11-09 (F-45 in `blueprint/context/findings.md`): the 16 logos
on that night's NBA slate cost 978,608 bytes as 500px PNGs, against 31,876 bytes
from ESPN's resizer at 40px. That is about 31 times the bytes, and about 16 MB
of decoded bitmaps against about 100 KB. At 104px (a 52px hero at 2x) the
resizer gave 3.8 to 9.5 KB per logo, against about 61 KB.

### The fix

`teamLogoUrl(sport, code, size)` takes the display size and returns ESPN's
resizer URL at twice that size, for sharp images on 2x screens:

`https://a.espncdn.com/combiner/i?img=/i/teamlogos/{sport}/500/{code}.png&w={2*size}&h={2*size}`

`TeamLogo` passes its `size` through. The resizer sends
`Access-Control-Allow-Origin: *` and serves NHL too.

**Decided 2026-11-09 (user):** the resizer serves every size, heroes included,
rather than the audit's suggestion to keep heroes on the 500px file. Heroes save
about 54 KB each too, and one rule is simpler than a size threshold.

Must not break:

- The NHL code overrides (`LAK` to `la`, `SJS` to `sj`, `TBL` to `tb`) and the
  per-sport override scoping.
- `null` for an empty or blank code.
- `TeamLogo`'s `onError` fallback: a failed image still shows the code badge,
  or nothing with `fallback="none"`. A resizer outage degrades the same way a
  missing file does today.
- The `width`/`height` attributes and CSS sizes stay the display size, not the
  2x fetch size.

### Build steps

- [x] **Step 1 - Size-aware logo URL** - give `teamLogoUrl` a `size` parameter
  that builds the resizer URL at `2 * size` (rounded to a whole pixel), pass
  `size` from `TeamLogo.tsx`, and update `web/src/utils/teamLogo.test.ts`: the
  resizer URL with doubled dimensions at 16 and 52, the NHL overrides and their
  sport scoping inside the resizer URL, and `null` for a blank code. *Done
  when:* the updated tests pass, `npm --prefix web run verify` passes, and on
  the local NBA slate every logo's `currentSrc` is a `combiner` URL with
  `w=32&h=32` and its natural size is 32x32.

### Verify

- `npm --prefix web run verify` passes (typecheck, tests, build). No API file
  changes, so `pytest` is not needed.
- In the browser, on the NBA and NHL slates, the home page and one game page per
  sport: every logo shows, is sharp, and the network panel shows small
  `combiner` PNGs instead of `/500/` files. The NHL slate includes an override
  team (LA, SJ or TB) when one is playing.
- Block `a.espncdn.com` in the browser: rows fall back to the bare code and
  heroes to the code badge, as before.

### Outcome

Completed 2026-11-09 on `fix/team-logo-size`.

- `teamLogoUrl(sport, code, size)` returns ESPN's combiner URL at `2 * size`
  (rounded) for every slot, and `TeamLogo` passes its `size`. Display sizes,
  the NHL overrides and the `onError` fallback are unchanged.
- Browser (local dev server, hidden pane, so each `src` was loaded directly):
  the NBA slate's 16 logos are all `combiner` URLs with `w=32&h=32` and load at
  32x32; the NHL slate's 6 (including the `sj` override) load at 32x32; the
  LAL @ ATL game hero's two load at 104x104.
- Verify: `npm --prefix web run verify` (96 files, 1,447 tests, typecheck,
  build) and `python -m pytest` from `api/` (6,043 passed).
- Not checked: the logos by eye, and the blocked-CDN fallback.
- F-45 is `fixed` in the ledger; a later `/audit` closes it with F-43 and F-44.
