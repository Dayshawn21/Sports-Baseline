# Feature: Analysis workspace and chart style

**From build-plan:** feature 46a (parent 46, Analysis workspace)
**Status:** complete (2026-10-24)
**Branch:** `feature/46a-analysis-workspace`

## Goal

Create `analysis/` at the repo root: a self-contained notebook workspace for the
Numbers Behind the Game social account (@numbersbehindthegame, "sports analytics
for beginners"). It reads the existing database strictly read-only and exports
branded charts sized for phones. 46b (thumbnails) and 46c (the first notebook)
build on the style, database helper and template set here.

## Design reference

- Logo: `blueprint/reference/46a/logo.png` (1254x1254, opaque navy background).
  Step 1 copies it to `analysis/thumbnails/logo.png`.
  - Sampled colors: accent blue `#09BDFE`, logo background `#060D1A`, white `#FEFEFE`.
- Lineform tokens from `web/src/index.css`:
  - `--bg-app` `#000000`
  - `--bg-card` `#0d0d0f`
  - `--text-primary` `#f5f5f7`
  - `--text-secondary` `#9a9aa3`
  - `--text-muted` `#85858f`
  - `--chart-mid` `#6b6b75`
  - `--chart-low` `#3a3a42`
- Fonts: Barlow Condensed (titles), DM Sans (body), JetBrains Mono (numbers).
  They are downloaded once from Google Fonts (OFL) into `analysis/fonts/`, so
  rendering needs no network.

## In scope

- `analysis/README.md` covers:
  - Setup: Windows venv, install, Jupyter kernel.
  - How to run a notebook from a clean kernel.
  - The notebook template (9 sections).
  - The audience and language rules, word for word from the request.
  - The 12-week roadmap, the three recurring series, and the optional tennis
    event posts (dates marked "confirm before posting").
  - A thumbnail section stub that 46b fills in.
- `analysis/requirements.txt`. Versions are reused from `api/requirements.txt`
  where they overlap:
  - pandas 2.2.3, numpy 2.2.1, sqlalchemy 2.0.36, psycopg[binary] 3.2.4,
    python-dotenv 1.0.1, playwright 1.49.0
  - plus matplotlib, jupyter, pytest
  - plus `nfl_data_py==0.3.2`: 0.3.3 pins pandas<2, and 0.3.2 resolves cleanly.
  - plus `nba_api`
  - The new packages are pinned to exact versions resolved at install.
- `analysis/.venv`, a separate venv, already ignored by the root `.venv/` rule.
- `analysis/lib/db.py`: `read_engine()` returns a read-only SQLAlchemy engine.
- `analysis/lib/style.py`: the one chart style (contract below).
- `analysis/lib/glossary.md`: the entry format plus an empty "Terms" list. 46c
  adds the first terms.
- `analysis/templates/notebook-template.ipynb`: the 9 template sections as
  markdown cells, plus a parameters cell. Outputs cleared.
- `analysis/tools/check_notebooks.py`: fails if any `analysis/**/*.ipynb` has
  outputs, execution counts or secret-like strings.
- `analysis/tests/` for the pure logic, run with
  `analysis/.venv/Scripts/python -m pytest analysis/tests`.
- `analysis/examples/style_demo.py`: renders one sample chart, with made-up
  labeled data, at both sizes. It is for visual review.
- `.gitignore` additions: `analysis/output/`, `analysis/data/`,
  `.ipynb_checkpoints/`.

## Out of scope

- The thumbnail generator and its README section (46b).
- Any real analysis, `lib/nfl_team_report.py`, play-by-play caching and the
  first notebook (46c). The `analysis/data/` ignore rule lands now so 46c
  cannot leak cached files.
- Glossary terms. None are used until 46c.
- Adding analysis tests or dependencies to the Verify command or CI.
- Any change under `api/`, `web/`, `.github/`, `render.yaml`, or the database.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Skeleton, requirements, README, ignores.** Create:
  - the folders above
  - `analysis/thumbnails/logo.png`
  - `requirements.txt`
  - `README.md` (setup, run, template, rules, roadmap, series, tennis dates,
    thumbnail stub)
  - the glossary stub
  - the `.gitignore` additions

  Then create `analysis/.venv` with Python 3.11 and install.
  *Done when:*
  - `pip install -r analysis/requirements.txt` succeeds and `pip check` is clean.
  - `git check-ignore` confirms `analysis/output/x.png`, `analysis/data/x.parquet`
    and `analysis/.venv` are ignored.
  - The README contains all five rule groups and all 12 roadmap weeks.

- [x] **Step 2 - Read-only database helper.** `lib/db.py`:
  - `database_url()` takes `DATABASE_URL` from the environment, else loads it
    from `api/app/.env` (path resolved from the file location, not the working
    directory) with python-dotenv.
  - It normalizes any `postgresql://` or `+asyncpg`/`+psycopg_async` driver to
    sync `postgresql+psycopg://`.
  - It raises a clear error when the URL is missing. The URL is never printed or
    put in the error.
  - `read_engine()` sets `default_transaction_read_only=on` through connect
    `options`, so every transaction is read-only at the server, and `pool_pre_ping`.

  Tests cover URL normalization, the env-over-file precedence, a missing URL,
  and that the read-only option is present. No test connects.
  *Done when:*
  - The tests pass.
  - A one-off check shows `SELECT count(*) FROM sport_games WHERE sport = 'nfl'`
    returns rows.
  - `UPDATE sport_games SET season = season WHERE false` fails with
    "read-only transaction".

- [x] **Step 3 - Fonts and chart style.**
  - Download the static TTFs into `analysis/fonts/` with their `OFL.txt` files:
    Barlow Condensed 600 and 800, DM Sans 400 and 600, JetBrains Mono 500.
  - Write `lib/style.py` to the contract below.
  - Write `examples/style_demo.py`.

  Tests cover exact pixel sizes for both formats, highlight-versus-gray colors,
  the output path naming, and that a missing font raises instead of silently
  falling back.
  *Done when:*
  - The tests pass.
  - The demo writes `analysis/output/style-demo-feed.png` (1080x1350) and
    `style-demo-vertical.png` (1080x1920).
  - Both images, viewed, show these, with no matplotlib font-fallback warnings:
    - the answer-style title in Barlow Condensed
    - one bar in `#09BDFE` with the rest gray
    - numbers in JetBrains Mono
    - the source line
    - the logo tile plus @numbersbehindthegame
    - the minimum text sizes below

- [x] **Step 4 - Notebook template and the clean-notebook check.**
  - `templates/notebook-template.ipynb` contains:
    - a parameters cell (`TEAM`, `SEASON = None` meaning latest)
    - the 9 sections as markdown headings, with one-line prompts
    - a final "What I learned" cell
  - `tools/check_notebooks.py [paths]` exits 1 and names the file and cell on:
    - any output or execution count
    - `postgresql://` or `postgres://`
    - `DATABASE_URL=`
    - a 32+ character hex or base64 key-shaped token in source

  Tests use tiny in-memory notebook dicts.
  *Done when:*
  - The tests pass.
  - The check passes on the template and fails on a fixture with an output.
  - The README documents running it before every commit.

- [x] **Step 5 - Isolation proof.**
  *Done when:*
  - The full Verify command passes.
  - `git diff --stat master` lists only `analysis/`, `.gitignore` and
    `blueprint/` paths.
  - `grep -r "analysis" api/app web/src` finds no new import.
  - `python -m pytest analysis/tests` passes in the analysis venv.

## Files / areas

- New: `analysis/README.md`, `analysis/requirements.txt`
- New: `analysis/lib/__init__.py`, `analysis/lib/db.py`, `analysis/lib/style.py`,
  `analysis/lib/glossary.md`
- New: `analysis/fonts/*.ttf` and `OFL.txt` files, `analysis/thumbnails/logo.png`
- New: `analysis/templates/notebook-template.ipynb`,
  `analysis/tools/check_notebooks.py`, `analysis/examples/style_demo.py`
- New: `analysis/tests/test_db.py`, `test_style.py`, `test_check_notebooks.py`
- Changed: `.gitignore`

## Data / contracts

**`lib/style.py` (load-bearing for 46b and 46c):**

```python
ACCENT = "#09BDFE"            # logo blue: the one highlight color
BG = "#000000"                # --bg-app
TEXT = "#f5f5f7"              # --text-primary
TEXT_2 = "#9a9aa3"            # --text-secondary
GRAY = "#6b6b75"              # --chart-mid: everything not the point
GRAY_LOW = "#3a3a42"          # --chart-low: gridlines, baselines
SIZES = {"feed": (1080, 1350), "vertical": (1080, 1920)}
HANDLE = "@numbersbehindthegame"

def apply_style() -> None                      # registers bundled fonts, sets rcParams
def new_figure(size: Literal["feed", "vertical"]) -> tuple[Figure, Axes]
def highlight(labels: Sequence[str], keys: Collection[str]) -> list[str]  # ACCENT or GRAY per label
def finish(fig, ax, *, title: str, source: str, subtitle: str | None = None) -> None
def export(fig, name: str, size: Literal["feed", "vertical"]) -> Path    # analysis/output/<name>-<size>.png
```

- **Pixel sizes are exact.** `dpi=100` with figsize taken from `SIZES`.
  `export` never uses `bbox_inches="tight"`, which would change the size.
- **Phone-readable minimums at export:**
  - title 64 px or larger (Barlow Condensed 800, at most 2 lines, wrapped)
  - subtitle and labels 34 px or larger (DM Sans)
  - tick numbers 30 px or larger (JetBrains Mono)
  - source line and handle 26 px or larger
- **Layout:**
  - The title band is at the top. In the vertical format, content stays clear
    of the top 220 px and the bottom 380 px, which are the TikTok/Reels UI zones.
  - The source line sits bottom-left: "Source: <name> · data through <week or date>".
  - The credit sits bottom-right. The logo is a rounded tile at about 56 px,
    since its navy background is opaque, followed by the handle in `TEXT_2`.
- **Fonts:** `apply_style` raises `FileNotFoundError` naming the missing TTF.
  It never falls back to DejaVu.

**`lib/db.py` (load-bearing for 46c):** `read_engine() -> Engine` (sync
SQLAlchemy). The read-only guarantee is enforced by the server
(`default_transaction_read_only`), not by convention. There is no write helper,
ever.

## Testing

- **Test runner:** pytest in `analysis/.venv`, `analysis/tests/`. It runs
  separately from Verify (agreed 2026-10-24), so CI never installs notebook
  dependencies.
- **Logic under test:**
  - `db.py`: URL resolution and normalization, the missing-URL error,
    read-only connect options.
  - `style.py`: sizes, highlight colors, export path, missing-font error.
  - `check_notebooks.py`: output and secret detection.
- **Not unit-tested:** chart appearance. It is reviewed from the demo PNGs.
- **Verify still runs** in Step 5, to prove the app is untouched.

## Notes for the AI

- No em dashes in any generated text (README, comments, templates). Keep comment
  density to the repo bar.
- Never read, print or commit the contents of `api/app/.env`. Tests use
  monkeypatched env vars and temp files only.
- Windows: create the venv with `py -3.11 -m venv analysis/.venv`. Playwright's
  browser install belongs to 46b.
- Some families may be variable fonts only in google/fonts (DM Sans, JetBrains
  Mono). If so, take static TTFs from the families' upstream releases (both OFL),
  because matplotlib renders variable fonts at their default instance. Commit
  each family's license.
- `analysis/` must not be importable from the app, and the app must not be
  imported by `analysis/`. `lib/db.py` reads the env file directly rather than
  importing `app.config`.
- `nfl_data_py` is installed now but first used in 46c. It is deprecated
  upstream. 46c wraps it in one loader function so it can be swapped for
  `nflreadpy` or direct nflverse downloads later.

## Completion evidence (2026-10-24)

- Verify (`npm --prefix web run verify && cd api && python -m pytest`): 903 web
  tests and build passed, 4,462 API tests passed.
- Analysis tests (`analysis/.venv/Scripts/python -m pytest analysis/tests`): 44
  passed, 5 of 5 runs after forcing the off-screen Agg backend in `conftest.py`.
- Live read through `read_engine()`: 3,935 NFL games; `UPDATE sport_games SET
  season = season WHERE false` refused with "cannot execute UPDATE in a
  read-only transaction".
- Demo charts rendered at exactly 1080x1350 and 1080x1920 with no font fallback.
- The template ran top to bottom from a clean kernel; `check_notebooks.py`
  passed it and failed a copy with an output (exit 1, cell named).
- Diff limited to `analysis/`, `.gitignore` and `blueprint/`; no imports between
  `analysis/` and the app in either direction.

**Deviations from the draft spec, approved at step review:**

- Read-only is enforced twice: server `default_transaction_read_only` plus
  psycopg `postgresql_readonly` (`BEGIN READ ONLY`), both proven through Neon's
  pooler.
- The vertical safe zone also keeps 140 px clear on the right (TikTok/Reels
  buttons). Titles longer than two lines raise instead of shrinking.
- The footer uses two rows (source line, then logo tile and handle).
- Fonts are static TTFs from the Google Fonts CSS API; matplotlib needs TTF.
