# 54a. Shell and NBA/NHL

**Status:** complete (2026-11-03)
**Branch:** `feature/player-page-shell`
**Parent:** 54 Shared player-page shell (54b NFL and 54c tennis follow)

## Goal

The NFL, NBA and NHL player pages look different because each page wraps its own copy of the
same frame. The NBA and NHL pages are near-duplicates: the same page container, loading and
not-found states, Back crumb slot, `PageHead` with a status line, injury line, empty-state
note and a market tab strip that differs only in types and labels. This step moves that frame
into two shared components and puts NBA and NHL on them, so 54b and 54c can move NFL and
tennis onto the same frame without copying it a third and fourth time.

The visible pages must not change in this step. It is a refactor with one contract (below).

## Scope

**In**
- `PlayerPageShell`: the page container, the Back crumb slot, the head (title, status line),
  the injury or availability slot, and the empty-state slot. Also the loading, error and
  not-found states those pages repeat (`PlayerPageState`, `NotFound`).
- `PlayerMarketTabs`: the "Props on ..." section title with its market count, the tab strip
  (`?market=`, replace navigation, `aria-current`) and the selected market's section as children.
- NBA and NHL pages and their prop-tab components use both. The per-sport crumb, injury tag,
  market section and form chart stay where they are.

**Out**
- The NFL page (54b) and the tennis page (54c).
- Renaming CSS classes. The strip already uses the `nfl-player-*` classes on all three sports;
  moving them to a neutral name is a later cleanup and would be a large diff for no visible change.
- Any change to data, hooks, endpoints, query keys, form chart, window switch or signal colors.
- Wording changes ("Props on <date>" stays), tab order, or what a market section shows.

## Contracts (load-bearing: 54b and 54c build on these)

```ts
// web/src/components/shared/PlayerMarketTabs.tsx
interface PlayerMarketTabsProps {
  heading: string                  // e.g. "Props on 2026-11-04"
  note?: string                    // replaces the market count beside the heading
  tabs: Array<{ key: string, label: string }>
  selectedIndex: number            // -1 when none selected
  hrefFor: (key: string) => string // the sport builds it with playerSearch
  children?: ReactNode             // the selected market's section
}

// web/src/components/shared/PlayerPageShell.tsx
interface PlayerPageShellProps {
  sportClass: string               // 'nba-player' | 'nhl-player', next to nfl-slate nfl-player
  crumb: ReactNode
  title: string
  meta?: ReactNode
  notice?: ReactNode               // the injury line
  children: ReactNode
}
```

- The tab strip returns `null` when there are no tabs, as both pages do today.
- `hrefFor` stays the sport's call so each page keeps its own `?date=` and `?market=` rules;
  the shared component never reads the URL.
- Section ids stay `prop-<market>` from `propSectionIds`, since the form chart and Back-restore rely on them.

## Build steps

- [x] **Step 1 - Shared tab strip.** Add `PlayerMarketTabs` and a tiny pure helper
  `marketCountLabel(count)` (`"2 markets"` / `"1 market"`) in `web/src/utils/playerPage.ts`
  with tests. `NbaPlayerPropTabs` and `NhlPlayerPropTabs` render through it and keep only
  their market lookup and labels.
  *Done when:* `npm --prefix web run verify` passes, the helper has tests for 1, 2 and 0, and
  the NBA and NHL pages' tab markup (heading text, link hrefs, `aria-current`) is identical to
  before on a live page.
- [x] **Step 2 - Shared page shell.** Add `PlayerPageShell` and move the container, the loading,
  error and not-found states, the crumb and injury slots and the empty-state note into it for
  NBA and NHL. Each page keeps its own `Crumb`, `InjuryLine` and copy.
  *Done when:* verify passes, and `NbaPlayerPage.tsx` and `NhlPlayerPage.tsx` no longer contain
  the repeated container and state markup.
- [x] **Step 3 - Prove nothing moved.** Compare each page before and after on a live player:
  heading text, tab labels, hrefs, injury line, not-found and loading messages, and the console.
  *Done when:* a before and after capture of the same NBA and NHL player match, and the
  console shows no new errors.

## Files and areas

- New: `web/src/components/shared/PlayerMarketTabs.tsx`, `web/src/components/shared/PlayerPageShell.tsx`,
  `web/src/utils/playerPage.ts`, `web/src/utils/playerPage.test.ts`
- Changed: `NbaPlayerPage.tsx`, `NhlPlayerPage.tsx`, `NbaPlayerPropTabs.tsx`, `NhlPlayerPropTabs.tsx`
- Untouched: `NflPlayerPage.tsx`, `TennisPlayerPage.tsx`, every API file, all CSS (classes are kept)

## Testing

- Logic: `marketCountLabel` gets a unit test. The components are layout only, so per the test
  gate they ride on the build and the Step 3 capture, not new component tests.
- Gate: `npm --prefix web run verify`. No API change, so `pytest` is not part of this step.

## Notes for the AI

- Display only. Do not touch projections, ranks, edges, versions, or the gray signal colors.
- Behavior must not change: if a diff alters visible text, a link or an id, it is wrong for this step.
- Keep the shared components sport-neutral: no NBA or NHL import in `components/shared/`.
- `playerSearch` and `propSectionIds` live in `utils/nflPlayer.ts` today and the NBA and NHL
  pages import them from there. Leave them; moving them is not this step.
- No em dashes in code, comments or commit messages. Comment only what the code cannot say.
