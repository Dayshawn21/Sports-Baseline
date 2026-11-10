# Feature: Team logos

**From build-plan:** feature 58
**Branch:** `feature/team-logos` (worktree `.claude/worktrees/58-team-logos`)
**Status:** complete (2026-11-09)

## Goal

Show NBA, NHL and NFL team logos beside the team codes on the slate rows, the
game-page heroes and the home sport cards, so a game reads at a glance. Display
only: no API, model, rank or gray-color change.

The player pages are being worked on in another checkout, so this feature must
not touch them (see Out of scope) and must merge cleanly beside that work.

## In scope

- A pure, tested URL helper that maps a sport and a stored team code to a logo
  URL on ESPN's keyless image CDN (`https://a.espncdn.com/i/teamlogos/{sport}/500/{code}.png`).
- One shared `TeamLogo` component: lazy-loaded, fixed size, and it falls back to
  the code badge when the image fails or the code is unknown.
- Logos on the NBA, NHL and NFL slate rows, the three game-page heroes, and the
  home sport cards' next-game lines.

## Out of scope

- **Player pages and headshots.** Never edit `NbaPlayerPage`, `NflPlayerPage`,
  `NhlPlayerPage`, `TennisPlayerPage`, any `*-player.css`, `PlayerPageShell`,
  `PlayerMarketTabs`, `PlayerContextSections`, `PlayerEvidence`,
  `PlayerHeadChips`, `PlayerProjectionHero` or any component under
  `components/*/` that a player page renders. Headshots need `source_player_id`
  exposed by the API and belong to a later feature.
- Tennis: players are not on teams. Country flags are a separate decision.
- Prop boards, the Ask drawer, model pages and tables other than the three slate
  tables (a logo there is a later, separate choice).
- Self-hosting or caching the images, and any API, schema or migration change.
- Dark or light logo variants (the app is dark-only; ESPN's 500px PNGs read on it,
  checked in the browser step).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Logo URL helper and tests** - `web/src/utils/teamLogo.ts` exporting `teamLogoUrl(sport, code)` and its test file. Done when: `npm run test` passes with cases for every sport, lower-casing, the NHL overrides `LAK`->`la`, `SJS`->`sj`, `TBL`->`tb`, and an empty or whitespace code returning `null`; no component imports it yet.
- [x] **Step 2 - Shared `TeamLogo` component** - `web/src/components/shared/TeamLogo.tsx` plus a small CSS file: `<img>` with `loading="lazy"`, `decoding="async"`, explicit width and height (no layout shift), empty `alt` because the code is always printed beside it, and an `onError` fallback that renders the code badge. Done when: `npm run build` passes and a throwaway render with a good code shows the logo and with a bad code shows the badge (checked in the browser, not committed).
- [x] **Step 3 - Game-page heroes** - put `TeamLogo` in the existing `nfl-game-badge` slot of `NbaGameHero`, `NhlGameHero` and `NflGameHero`; the badge becomes the fallback. Done when: one game page per sport shows both logos at the badge size, a blocked image (network off for the CDN) shows the old badge, and the hero text and record lines are unchanged.
- [x] **Step 4 - Slate rows** - a small logo before each code in the Game cell of `NbaSlateTable`, `NhlSlateTable` and `NflSlateTable`, scored rows included, through one shared `SlateMatchupTeams` component. Done when: each slate shows the logos, row height and the one-line layout are unchanged at 1440px, 800px and 520px, the link `aria-label` is unchanged, and an unplayed and a final row both render. Built: at 480px and narrower the row logos are hidden, because two logos clipped the records by up to 23px at 375px (the hero logos stay on every screen).
- [x] **Step 5 - Home sport cards** - `homeCard` splits its next-games text into segments (a tested `matchupSegment` reads the "AWAY @ HOME" title, so the shared `HomeNextGame` model and its other readers are unchanged; `next` is the segments joined, so its text is identical) and `HomeSportCard` renders logos in the "Next:" line. Done when: the NBA, NHL and NFL cards show logos beside their next games, an empty or failed slate still reads quiet, and the tennis card is unchanged. If the home model change proves larger than one reviewable diff, stop and split this step out rather than widening it.
- [x] **Step 6 - Verify and boundary check** - run the Verify command and check the diff stays out of the player pages. Done when: `npm --prefix web run verify && cd api && python -m pytest` passes and `git diff master --name-only` lists no file named in Out of scope. Evidence is the live browser measurements recorded in each step (no screenshots were saved to disk).

## Files / areas

- New: `web/src/utils/teamLogo.ts`, `web/src/utils/teamLogo.test.ts`, `web/src/components/shared/TeamLogo.tsx`, a small `team-logo.css` beside it.
- Edit: `web/src/components/nba/NbaGameHero.tsx`, `web/src/components/nhl/NhlGameHero.tsx`, `web/src/components/nfl/NflGameHero.tsx`.
- Edit: `web/src/components/nba/NbaSlateTable.tsx`, `web/src/components/nhl/NhlSlateTable.tsx`, `web/src/components/nfl/NflSlateTable.tsx` (NHL shares `nfl-slate-table.css`).
- Edit: `web/src/components/home/HomeSportCard.tsx`, `web/src/utils/home.ts` and its tests.
- Do not touch: anything listed under Out of scope.

## Data / contracts

- **Load-bearing:** `teamLogoUrl(sport: 'nba' | 'nhl' | 'nfl', code: string): string | null`. A later headshot helper and any future logo use go through it. It returns `null` for an empty code so callers show the badge.
- Codes come from the team codes the slate and game payloads already carry (`sport_teams.team_code`). I tested all 95 stored codes against the CDN on 2026-11-09: NBA (30) and NFL (32) all resolve; of NHL (33), only `LAK`, `SJS` and `TBL` 404 and need the overrides above.
- No API, schema, migration or stored-data change. Production has no Content-Security-Policy, so the cross-origin images load.

## Testing

- **Logic with tests:** `teamLogoUrl` (Step 1) and the home next-game model change (Step 5).
- **No component tests** (project standard): `TeamLogo`, the heroes, the tables and the cards are verified by running the app: logos present, fallback on a blocked image, no layout shift, unchanged row height, phone width.
- Final gate is the Verify command in `AGENTS.md`.

## Notes for the AI

- The images are third-party and unlicensed assets on ESPN's CDN: fine for this app, but always keep the code badge as the fallback so a removed or renamed file never leaves a hole.
- Match existing patterns: `~/` imports, shared components in `components/shared/`, theme variables from `index.css` rather than hex values, no inline comment noise (see `coding-standards.md`).
- `NflSlateTable` and `NbaSlateTable` render the code inside a `<Link>` with a screen-reader label; keep that text as the accessible name and leave the logo decorative.
- Check the diff against the Out of scope list before every checkpoint: another checkout is changing the player pages and shared player files, and a conflict there is the main risk.
- Do not run `/complete`, merge or push without a separate yes. Before merging, compare against whatever the player-page work has changed on `master` and say so.
