---
version: 1
slug: "web-src-pages-nflintelligencepage-tsx"
primary_target: "web/src/pages/NflIntelligencePage.tsx"
related_targets: ["web/src/pages/TennisIntelligencePage.tsx","web/src/pages/NbaSlatePage.tsx","web/src/App.tsx"]
---

# Slate surface brief

**Scope:** the slate pattern shared by every sport (`/`, `/nfl`, `/nba`), plus
the app shell (top bar) every page inherits. Mode: Operate.

**Audience and job:** the owner, finding today's plays and opening one game;
desktop and phone equally. Secondary: demo visitors who must tell picks from
reference.

**Constraints:** incumbent tokens kept; signal colors only for validated
signals (NFL and NBA gaps stay gray); 11px floor; display never changes a
probability, edge, rank, sort or pick; times in `CT`.

## Direction contract

THESIS: The slate is a search-first ledger. One command field reaches any game,
team or player, and every game is one dense row. It refuses a card per game and
a different page shape per sport.

OWN-WORLD: The incumbent Lineform world: true-black ground, near-black panels,
hairline borders, three gray text tiers, green and red only as validated
signals, Barlow Condensed display, DM Sans body, JetBrains Mono numerics. Rows,
not cards; the plays digest is the only boxed strip.

STORY: The owner sees the period's biggest gaps first, labeled pick or
reference, scans every game in one table, and types to jump to a team, player
or game. A visitor sees at a glance which numbers are picks.

FIRST VIEWPORT: 64px top bar: logo, sport tabs, command field (up to 620px,
`/` focuses it), then Slate / Props / Model / How it works. Page head: title,
period line, previous and next. A four-up plays digest. Then one table grouped
by start window: start, game with records, spread, total, moneyline, muted
model, prop count, note tags; a row opens the game page. Phone: the command
field collapses to a search button that expands full width, the digest scrolls
sideways, rows become two lines.

FORM: Command bar + plays digest, position 7 of 7 on the ranked list,
seed:cbce053edc642c82. Signature interaction: typing filters the table live
and offers jump targets; Enter opens the top match.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Tennis's digest content (priced picks, green) versus NFL and NBA (largest
  gaps, gray): same strip, different signal rule.
- Whether Props and Model pages adopt the same table-first shape in this item
  or a later one.
