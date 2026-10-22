# NFL chart readability and matchup research context

Type: Fix

## Scope

Record the accumulated changes requested and reviewed in this conversation.
The user authorized final audit, archiving and one local commit on 2026-10-22.
Merge, push and deployment are outside that authorization.

## Problem and approach

NFL charts required hovering to read values, and the matchup page lacked recent
team volume comparisons and explanations. Add readable bar labels, season versus
last-three team stats, an optional guide, expanded stored injury reports and
market-derived team points. Keep all new information descriptive and gray.

## Completed steps

- [x] Show weekly usage values and percentages above taller bars, with season
  spacing, week labels and unchanged zero/missing-data distinctions.
- [x] Show NFL prop recent values, opponent labels and a labeled current line,
  preserving shared chart defaults and history-popover keyboard behavior.
- [x] Add team pass/rush attempts made and allowed, and compare season averages
  with each team's last three completed regular-season games before the selected
  week. Show metric coverage and season ranks; retain play-weighted rate math.
- [x] Add a collapsed guide above both game tabs and explain coverage, ranks,
  recent windows and defensive production allowed near the table.
- [x] Expand the stored injury report to all positions, group position units,
  retain reporting-team identity and meaningful-status filtering, and label
  stored update times without claiming official report freshness or health.
- [x] Derive both teams' market-implied points from the displayed book's spread
  and total. Preserve quarter points and show unavailable states for bad inputs.

## Done when and verification

- All values and explanations are visible on desktop and phone layouts.
- The guide and injury disclosures work from the keyboard; history popovers
  open and dismiss with Escape.
- Tests cover recent-window ordering, partial coverage, zeros, side mapping,
  injury grouping, spread signs, missing odds and quarter-point totals.
- The documented Verify command passes with the API virtual environment active.
- The employer interview guide is updated locally and remains ignored.

## Boundaries

No model, ranking, recommendation, probability, fit, holdout evaluation, database schema,
paid provider call or shared-database write is part of this work. Passing and
rushing EPA splits remain deferred. Hosted deployment remains unverified.

## Manual try path

Open `http://localhost:3001/#/nfl/game/94`. Expand the guide, then select Matchup
to compare team stats, implied points and expanded injuries. Select Player Props
to read labeled Last 5 charts and open a player for weekly usage values.

## Completion evidence, 2026-10-22

User authorization: final audit, archive the accumulated changes and make one
local commit. No merge, push, deployment or remote modification was authorized.

### Final automated gate

`npm --prefix web run verify && cd api && python -m pytest`

Executed from the repository root through cmd with `api/.venv` activated. Exit 0
on the final run after the audit repair: TypeScript passed, 57 web test files and
815 web tests passed, Vite production build passed, and 3,713 API tests passed.
Existing warnings: the Vite bundle-size advisory and Starlette's deprecated
AnyIO BlockingPortal alias. No focused or skipped test was added by this change.
`git diff --check` passed.

### Behavioral evidence

- Real stored 2026 Week 7 NE at CHI data: NE pass attempts 31.5 across 6/6 games,
  last three 34.3 across 3/3 games. The notes read covered 14 scheduled matchups.
- The expanded live injury response contains 13 entries for NE at CHI: one
  offensive skill player, three offensive linemen and nine defenders. Stored
  timestamps are present and explicitly distinguished from official report time.
- The displayed DraftKings spread and total imply NE 23.75 and CHI 26.75 points.
  Browser-controlled missing spread and empty injury responses show unavailable
  values and do not claim that either roster is healthy.
- Live route: `http://localhost:3001/#/nfl/game/94`. Desktop 1440px and phone
  390px layouts fit; guide and injury disclosures work from the keyboard.
  Recent-game chart history opens and dismisses with Escape.
- Weekly usage component previews checked ordinary values, zero, unavailable
  snaps, percentages and the season break at desktop and phone widths.
- F-13 narrow-screen repair: at 320px the table retains about 60px for metric
  labels and scrolls within its matchup half, with no document overflow.
- Browser screenshots were inspected from the system temporary directory.
  They are review artifacts and are not part of the public repository.

### Audit and invariants review

Scope: all staged/unstaged changes and the new NflDataGuide source on
`fix/nfl-bar-value-labels`, against master at merge base
`3e67644d3eb3ec758633ae12b8bf9fdfb7adee74`. There were no branch-only commits.
Reviewed changed backend core, repository, schema and service paths; web pages,
components, shared chart styles, helpers and related tests. Lenses: quality,
security, performance and tests. Dependencies, generated build output and the
rest of the application were outside the audit scope.

One confirmed P2 finding was repaired and re-reviewed below; no other finding
was confirmed in this scope. Existing F-09 and F-12 remain unverified and are
unmodified in the live ledger. No P0/P1 finding blocks this completion.

Sport and regular-season filters remain on team-game reads; the stored injury
joins retain NFL sport filters and reporting-team identity. The odds provider
selection is unchanged. Core remains pure and SQL remains in repositories.
No projection version, grading rule, fit, model, recommendation or signal-color
adoption changed. No holdout results were read or scored. Additional aggregation
uses the same bounded season team-game query, not a new heavy report or N+1 read.
No workflow/adaptor files changed. No credentials were added. This review did
not run a dependency vulnerability scan or establish hosted memory acceptance.

The local ignored employer interview guide was updated and was not staged.
No shared-database write, migration or paid provider request was performed.
Hosted deployment is unverified. Passing/rushing EPA splits remain deferred.

## Findings

### nfl-chart-and-matchup-context/F-13 [P2] closed - Narrow matchup tables squeeze metric labels to zero width

**File:** web/src/pages/nfl-game.css:162
**Found:** 2026-10-22 by /audit (scope: changed NFL charts and matchup context; lenses: quality, security, performance, tests)
**Why it matters:** At a 320px viewport the matchup table's four fixed numeric
columns require 248px inside a 246px parent, leaving the metric-label column
zero width. Labels extend into numeric cells even though the document itself
does not overflow. Reproduced on the live local NE at CHI matchup.
**Suggested fix:** Give the table a readable minimum width and contain horizontal
scrolling inside its matchup half, preserving the wider desktop and phone layout.
**Resolution:** Repaired with a 308px table minimum and horizontal scrolling
inside each matchup half. Re-review on the live local page at 1440px, 390px and
320px confirmed label widths of about 206px, 68px and 60px respectively, no
document overflow, and working contained scrolling at 320px. The guide and
history popover keyboard controls also passed. Closed on 2026-10-22.
