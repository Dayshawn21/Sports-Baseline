# Feature: Thumbnail generator

**From build-plan:** feature 46b (parent 46, Analysis workspace)
**Status:** complete (2026-10-24)
**Branch:** `feature/46b-thumbnail-generator`

## Goal

One command turns a small JSON config into branded thumbnails for every
platform:

```
analysis/.venv/Scripts/python analysis/thumbnails/make_thumbnail.py --config <file.json>
```

The look lives in an HTML/CSS template, so the owner can restyle it like a web
page. Playwright renders it to PNG fully offline, with fonts loaded from
`analysis/fonts/`. 46c's notebook writes one config per team and calls the
same renderer.

## Design reference

- No mockup exists. Step 2's first render is the visual reference, reviewed
  before the other formats are built on it.
- Brand tokens come from `analysis/lib/style.py`:
  - `ACCENT` `#09BDFE`
  - `BG`, `TEXT`, `TEXT_2`, `GRAY`
  - the three bundled fonts
  - the logo at `analysis/thumbnails/logo.png`

  The renderer injects them as CSS variables, so there is one source of truth.
  `template.css` keeps the same values as fallbacks, so the file can be opened
  directly in a browser while editing.
- The owner's look rules:
  - huge high-contrast uppercase headline, 2 lines at most, shrinks to fit
  - logo and handle in a small corner tag
  - no team logos or player photos
  - plain dark gradient unless a background image is given

## In scope

- `analysis/thumbnails/config.py` (pure):
  - `load_config(path)` returns a validated `ThumbnailConfig`
  - the `FORMATS` table: sizes and safe boxes per platform
  - `output_path(name, format)`
- `analysis/thumbnails/template.html` and `template.css`: one template, with
  the layout switched by a `data-format` attribute on `<html>`.
- `analysis/thumbnails/make_thumbnail.py`:
  - the CLI (`--config`, optional `--formats youtube,vertical,feed`)
  - `render(config) -> list[Path]`
  - offline rendering: every non-`file:` request is aborted
  - waits for fonts to load, checks that the headline fits, then screenshots
    each format
- `analysis/thumbnails/configs/sample.json`: an example config using
  `style-demo-feed.png` from 46a. Configs are small and committed, so every
  thumbnail can be reproduced.
- Outputs go to `analysis/output/thumbnails/<name>-<format>.png` (already
  ignored by git).
- Notebook template:
  - section 7 gets a real cell that writes a config to `thumbnails/configs/`
    and calls `render`
  - all `<...>` placeholders become `[...]`: markdown treats `<...>` as an HTML
    tag and hides it (found in the 46a manual test)
- README: the "Make a thumbnail" section (command, config fields, formats and
  safe zones, editing the template, the no-logos/no-photos rule).
- One-time setup: `python -m playwright install chromium` in the analysis
  venv, added to the README setup steps.

## Out of scope

- Real thumbnails for DAL and PHI, and their configs (46c).
- Animated or video covers, and text effects beyond CSS (shadows and outline
  are fine).
- Any check of what a background image shows. The no-logos/no-photos rule is
  documented, but the owner chooses the images.
- Changes under `api/`, `web/`, `.github/`, or to the database. The renderer
  never connects to the database.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Config, formats and browser.**
  - `config.py`, with the contract below.
  - `configs/sample.json`.
  - Tests for:
    - headline word count (3 to 5)
    - sport must be `nfl`, `nba` or `tennis`
    - the chart file must exist under `analysis/output/` and be a PNG
    - a background path, if given, is resolved next to the config file and
      must exist
    - callout shape
    - name slug and its default from the config filename
    - output paths
    - every safe box lies inside its canvas
  - Install Chromium for Playwright 1.49 in the analysis venv.

  *Done when:*
  - The tests pass.
  - `load_config("analysis/thumbnails/configs/sample.json")` returns a config.
  - A headless Chromium launch prints its version.

- [x] **Step 2 - Template and YouTube render.**
  - `template.html` and `template.css`.
  - `make_thumbnail.py` rendering the `youtube` format only.
  - Tokens and font paths are injected from `style.py`.
  - The headline shrinks in JavaScript and reports
    `{fits, fontPx, lines}` back to Python.
  - All network requests are blocked.

  *Done when:*
  - The command writes `sample-youtube.png` at exactly 1280x720 after running
    the 46a style demo.
  - The run log shows zero non-file requests attempted, or each one aborted
    and named.
  - The image, viewed, shows:
    - an uppercase headline of 2 lines at most, in Barlow Condensed
    - the chart card
    - the sport tag
    - the logo and handle corner tag
    - the stat callout in JetBrains Mono and the accent blue
    - nothing in the bottom-right timestamp box

- [x] **Step 3 - Vertical and feed layouts, overflow error.**
  - Add the `vertical` and `feed` layouts.
  - A headline that cannot fit in 2 lines at the minimum size fails the run
    with exit code 1 and a message to shorten it. No partial PNG is written
    for that format.

  *Done when:*
  - The sample renders all three files at their exact sizes.
  - Each image, viewed, keeps the headline, chart, callout and corner tag
    inside its safe box.
  - Render tests pass, each skipped if Chromium is missing:
    - a long 5-word headline shrinks but stays at 2 lines
    - an overflowing headline raises
    - no network request is made
  - A version with `background` set renders the image under a dark overlay.

- [x] **Step 4 - Notebook template and README.**
  - The section 7 thumbnail cell.
  - The `[...]` placeholder fix.
  - The README "Make a thumbnail" section and the Chromium setup line.

  *Done when:*
  - A copy of the template run from a clean kernel writes 2 charts and 3
    thumbnails.
  - The copy and its outputs are deleted afterward.
  - The heading placeholder is visible in VS Code's notebook view.
  - `check_notebooks.py` passes on the template.

- [x] **Step 5 - Isolation proof.**
  *Done when:*
  - Verify passes.
  - `analysis/tests` passes.
  - `git diff --stat master` lists only `analysis/` and `blueprint/` paths.
  - No `api/` or `web/` imports.

## Files / areas

- New: `analysis/thumbnails/config.py`, `make_thumbnail.py`, `template.html`,
  `template.css`, `__init__.py`, `configs/sample.json`
- New: `analysis/tests/test_thumbnail_config.py`,
  `analysis/tests/test_thumbnail_render.py`
- Changed: `analysis/templates/notebook-template.ipynb`, `analysis/README.md`

## Data / contracts

**Config file (load-bearing for 46c):**

```json
{
  "headline": "CAN DALLAS SAVE IT?",
  "subline": "Week 7 check-in",
  "chart": "week01-dal-feed.png",
  "sport": "nfl",
  "callout": {"value": "+1.8", "label": "wins better than their record"},
  "background": "backgrounds/stadium-dark.jpg",
  "name": "week01-dal"
}
```

| Field | Required | Rule |
|---|---|---|
| `headline` | yes | 3 to 5 words. Shown uppercase. |
| `subline` | no | 60 characters at most |
| `chart` | yes | A PNG file name inside `analysis/output/` |
| `sport` | yes | `nfl`, `nba` or `tennis`. Sets the tag text (NFL, NBA, TENNIS). |
| `callout` | no | `value` up to 8 characters, `label` up to 40 |
| `background` | no | Path relative to the config file. It sits behind a dark overlay. Without it, the canvas uses a dark gradient from `BG` to the logo navy `#060D1A`. |
| `name` | no | Lowercase slug; defaults to the config file name |

Unknown keys are an error, so a typo can't be silently ignored.

**Python API (load-bearing for 46c):**

```python
@dataclass(frozen=True)
class ThumbnailConfig:
    headline: str
    chart: Path              # resolved, absolute
    sport: Literal["nfl", "nba", "tennis"]
    name: str
    subline: str | None = None
    callout: Callout | None = None
    background: Path | None = None

def load_config(path: Path) -> ThumbnailConfig
def render(config: ThumbnailConfig, formats: Sequence[str] = FORMAT_NAMES) -> list[Path]
```

**Formats and safe boxes** (px, top/right/bottom/left). Key content stays
inside the safe box:

| Format | Size | Safe insets | Why |
|---|---|---|---|
| `youtube` | 1280x720 | 56 / 64 / 56 / 64, plus a clear 240x110 box in the bottom-right corner | Video length badge |
| `vertical` | 1080x1920 | 240 / 140 / 420 / 60 | TikTok/Reels top bar, caption and buttons; the 3:4 profile-grid crop removes 240 at the top and bottom |
| `feed` | 1080x1350 | 60 / 80 / 60 / 80 | The 3:4 Instagram grid crop trims about 34 px per side |

**Headline fit:**
- Text starts at the format's maximum size: youtube 132 px, vertical 150 px,
  feed 140 px.
- It steps down 4 px at a time until it fits the headline box in 2 lines.
- Below 64 px it fails rather than shrinking further.

## Testing

- **Runner:** pytest in `analysis/.venv` (`analysis/tests`), outside Verify,
  as in 46a.
- **Unit tests, pure:**
  - config validation and every error message
  - name defaulting
  - output paths
  - safe boxes inside each canvas
- **Render tests:**
  - skipped with a clear reason when Chromium is not installed
  - cover exact output sizes, headline shrinking, overflow failure, and that
    no network request is made
- **Appearance:** reviewed from the rendered PNGs at each step. Not
  unit-tested.

## Notes for the AI

- Load fonts with `@font-face` from `file:` URLs to `analysis/fonts/*.ttf`.
  Before measuring, wait for `document.fonts.ready` and check
  `document.fonts.check` for each family. A missing font fails the run; it
  never falls back.
- Load the template from its `file:` URL and pass the config through
  `page.evaluate`. Never build HTML by string concatenation: user text goes in
  through `textContent`, never `innerHTML`.
- Block network with `page.route("**/*")`, letting only `file:` URLs
  continue. Log and count any aborted URL.
- Uppercase the headline with CSS `text-transform`. The config keeps the
  user's text as typed.
- No em dashes, en dashes or ellipsis characters in generated text. Comments
  should be as sparse as in 46a.
- `make_thumbnail.py` must run both as a script and when imported from a
  notebook in `analysis/`, putting `analysis/` on `sys.path` the way
  `style_demo.py` does.

## Completion evidence (2026-10-24)

- Verify (`npm --prefix web run verify && cd api && python -m pytest`): 903 web
  tests and build passed, 4,462 API tests passed.
- Analysis tests (`analysis/.venv/Scripts/python -m pytest analysis/tests`): 71
  passed, including real Chromium renders (Chromium 131.0.6778.33, Playwright
  1.49 headless shell, installed per machine).
- `make_thumbnail.py --config analysis/thumbnails/configs/sample.json` wrote
  1280x720, 1080x1920 and 1080x1350 PNGs (headline 116 / 150 / 140 px) with
  `network requests blocked: 0`. A too-long headline and a missing config each
  exit 1 with a plain message and write nothing; a background image renders
  under the dark overlay.
- The notebook template ran top to bottom through a real Jupyter kernel
  (nbconvert, sandbox lifted for that one command with owner approval): 2
  charts and 3 thumbnails, no errors. Test copies and outputs were deleted.
- Diff limited to `analysis/` and `blueprint/`; no imports between `analysis/`
  and the app.

**Found and fixed during the build:**

- Jupyter runs an event loop and Playwright's sync API refuses to start inside
  one, so `render()` moves to a worker thread when a loop is running (tested).
- The template's setup cell now finds `analysis/` from the notebook folder, a
  subfolder or the repo root; running the template in `templates/` failed with
  `No module named 'lib'` in the owner's VS Code run.
- `<...>` placeholders became `[...]`, since notebook markdown hid them as tags.
- A missing config file is a clean error rather than a traceback.

**Decisions:** the chart card stays left-aligned in the vertical and feed
layouts (owner, 2026-10-24). The no-logos/no-photos rule is documented; the
generator cannot check image content.
