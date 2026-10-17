# Fix: Label serve stats by what they measure

**Type:** Fix
**Status:** complete (2026-09-29)
**Branch:** `fix/serve-stat-labels`

## The problem

Three of the rolling serve stats are stored under names that do not match what
ingest computes (`app/ingest/player_stats.py`, formulas in its module docstring):

| Column / field | Name suggests | Actually stored |
|---|---|---|
| `aces_per_game` / `acesPerGame` | aces per game | aces per serve point (ace rate, TennisAbstract A%) |
| `df_per_game` / `dfPerGame` | double faults per game | double faults per serve point (DF rate, DF%) |
| `break_pct` / `breakPct` | share of return games broken | break points converted / break points created |

Two panels show them under the misleading names, and print the two rates as
raw decimals:

- **Slate match panel** (`web/src/components/tennis/TennisCommandCenter.tsx`,
  `InlineAnalysis`): "Aces / game 0.16", "DF / game 0.03", "Break rate 38%".
- **Prop board evidence panel**
  (`web/src/components/tennis/TennisPropEvidencePanel.tsx`, `FormStats`): the
  same three labels and the same raw decimals.

So Hurkacz's 15.9% ace rate reads as "0.16 aces per game", and a 38%
break-point conversion reads as breaking serve in 38% of return games. The match
page sidebar (32a) already labels them correctly as "Ace rate" and "BP
converted".

## The fix

Relabel and reformat in both panels, matching the 32a sidebar:

| Field | Label | Format |
|---|---|---|
| `acesPerGame` | Ace rate | percent, 1 decimal (15.9%) |
| `dfPerGame` | DF rate | percent, 1 decimal (3.2%) |
| `breakPct` | BP converted | percent, as today |

Must not break:

- **Values stay the same.** Only the label and formatting change: the same
  fields, the same players, the same order of rows.
- **No backend change.** The column names stay as they are. Renaming them
  would need a migration and would touch the prop projection code that reads
  `aces_per_game` as a per-point rate. It is out of scope; noted for item 17.
- **Colors unchanged.** Neither panel colors these rows.

## Build steps

- [x] **Step 1 - Relabel both panels** - in `InlineAnalysis`, change the three
  labels and show ace and DF rate through `fmtPct(value)` instead of raw
  `toFixed(2)`. Drop the `raw` flag from `Measure` if nothing else uses it. In
  `FormStats`, change the same three labels and format the two rates as
  percents with one decimal. *Done when:* `npm run build` and `npm run test`
  pass, and screenshots of both panels for the same match show "Ace rate",
  "DF rate" and "BP converted" with percent values that match the match
  page sidebar (for example Hurkacz 15.9%, `#/tennis/match/82863`).

## Verify

1. On the Tennis slate, select a match and read the "Serve and return" block
   in the side panel.
2. On the Tennis prop board, open a line and read "Serve & return" in the
   evidence panel.
3. Both show "Ace rate", "DF rate" and "BP converted", with ace and DF rates as
   percents (for example 15.9%, not 0.16). The values should match the same
   players' serve and return card on `/tennis/match/:id`.

## Notes for the AI

- UI-only change: build plus screenshots are the evidence, and there is no
  new logic to unit-test. If a shared formatter is extracted, it gets a Vitest
  test.
- Leave `app/core/` and the ingest untouched.
- No em dashes in comments.
