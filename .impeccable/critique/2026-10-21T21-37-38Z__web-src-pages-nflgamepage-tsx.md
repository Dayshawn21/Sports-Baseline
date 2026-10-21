---
target: NFL game page
total_score: 27
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\daysh\\OneDrive\\Desktop\\SportAppV2\\web\\src\\pages\\NflGamePage.tsx"
target_fingerprint: "sha256:3c0cd3fee034e84e9fb506eb45725ec49529b033df7ba1f28c77c7b1279fada9"
target_path: "C:\\Users\\daysh\\OneDrive\\Desktop\\SportAppV2\\web\\src\\pages\\NflGamePage.tsx"
timestamp: 2026-10-21T21-37-38Z
slug: web-src-pages-nflgamepage-tsx
closed: true
---
Method: dual-agent (A: /root/design_review; B: /root/detector_review)

# NFL game page design critique

Target: web/src/pages/NflGamePage.tsx, game 94 on localhost:3001.
Desktop 1440x1000 and mobile 390x844 inspected. No application code changed.

## Overall impression and specificity

27/40, Acceptable. The page feels authored for Lineform: quiet market comparisons,
monospaced numbers and gray unvalidated signals suit betting research. Preserve
the palette, fonts and signal rules. The biggest opportunity is a shorter mobile
research path with earlier injury context, rather than a visual redesign.

## Design health

| Heuristic | Score | Main observation |
|---|---:|---|
| System status | 3 | Status, loading and counts are visible. |
| Real-world language | 3 | Familiar markets; rateable and slice need translation. |
| User control | 3 | Backlink, filters and drawer close are present. |
| Consistency | 3 | Cohesive tables; player-name destinations differ. |
| Error prevention | 3 | Honest caveats; mobile injury context arrives late. |
| Recognition | 2 | Recent values depend on hover titles. |
| Efficiency | 2 | Long page without local section navigation. |
| Minimalist design | 3 | Calm visual system, some unnecessary controls/detail. |
| Error recovery | 2 | Some secondary errors lack a local retry. |
| Help | 3 | Help exists, important explanations remain technical. |
| Total | 27/40 | Acceptable |

## What works

- Clear market/model comparison and aligned prop figures.
- Gray signals and explicit reference caveats preserve honest model framing.
- Market grouping and evidence drawers support focused player research.

## Priority issues

1. [P1] Mobile injury and depth context follows the full prop list. At 390px,
   Props begins at y2119 and runs 5987px; sidebar notes begin at y8124.
   Put a compact injury/depth summary before Props on mobile, retaining the
   desktop sidebar. Suggested command: impeccable adapt.
2. [P2] Position filter touch targets are too narrow: All 15x40, QB 18x40,
   RB 16x40, WR 21x40, TE 15x40 and K 8x40. Provide generous padding and
   approximately 44px hit areas. Suggested command: impeccable adapt.
3. [P2] Recent-game bars place individual values/opponents in title attributes
   on unfocusable spans. Provide equivalent tap/focus access or a meaningful
   text summary. This is source evidence, not a screen-reader runtime result.
   Suggested command: impeccable harden.
4. [P2] Six secondary Other lines market tables remain expanded with Show all
   lines off, lengthening an 8639px mobile page. The switch controls a different
   set of rows, so this is unclear scope rather than broken behavior. Collapse
   reference markets under a labeled disclosure, clarify the toggle, and turn
   the sole Full game option into a static label. Suggested command: impeccable distill.
5. [P2] The Props note explains internal validation using ranking check and
   adopts a slice, at 11px. Explain research comparison versus recommendation
   directly, with methodology available on demand. Preserve factual status and
   ranking semantics. Suggested command: impeccable clarify.

## Cognitive load and emotional journey

Moderate load: hierarchy, choice density and progressive disclosure need work.
The six familiar position categories do not automatically warrant a hidden menu.
The opening is credible and calm; the long mobile ledger adds effort before
injury context. Earlier context and less default reference detail would improve
the finish without implying stronger betting signals.

## Persona red flags

- Power user: excessive travel between markets, props and player context.
- Keyboard/low-vision user: hover-only recent values and compact explanations.
- Mobile user: tiny position targets and injury notes far down the page.

## Detector evidence

CLI scan of the page and NFL components found zero issues. Browser injection
reported 17 flags: 13 tiny-text, one column-overflow, two assembled SVG and one
clip-path. The 11px text meets the product floor, so it is a readability concern,
not an automatic violation. The SVG findings refer to TanStack devtools, not
product illustration. The clip-path flag is unverified and excluded. The long
column flag agrees with observed page length, but does not prove horizontal
overflow; the mobile document width equals the 390px viewport.

## Minor observations

H1/Q1 are correctly hidden. Empty-state copy still mentions a period choice.
No tonal mismatch justifies replacing the established dark visual identity.

## Questions to consider

- Prioritize mobile context and targets, or prop clarity and reduced detail?
- Address the top three issues, or all five?
