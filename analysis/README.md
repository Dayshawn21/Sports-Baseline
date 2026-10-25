# Numbers Behind the Game: analysis workspace

Notebooks behind **@numbersbehindthegame**, sports analytics for beginners. Each
notebook asks one question, teaches one concept, answers it from Lineform's data
(plus free public data when needed), and exports charts, thumbnails and draft
posts.

This folder is outside the Lineform app. Nothing here is imported by `api/` or
`web/`, and nothing here changes the app, its models, its probabilities, its
picks or its database. The database connection is read-only at the server, so a
write fails even by accident.

## Setup (Windows, once)

From the repo root:

```powershell
py -3.11 -m venv analysis/.venv
analysis/.venv/Scripts/python -m pip install -r analysis/requirements.txt
analysis/.venv/Scripts/python -m ipykernel install --user --name nbtg --display-name "Numbers Behind the Game"
analysis/.venv/Scripts/python -m playwright install chromium
```

The last line downloads the browser the thumbnail generator renders with (once
per machine).

The database URL comes from `DATABASE_URL` in your environment, or else from
`api/app/.env`, the file the app already uses. Never paste it into a notebook.

## Run a notebook

1. Start Jupyter: `analysis/.venv/Scripts/jupyter lab analysis`
2. Open the notebook and pick the **Numbers Behind the Game** kernel.
3. Set the parameters in the first cell (for example `TEAM = "DAL"`).
4. **Kernel > Restart Kernel and Run All Cells.** A notebook counts as working
   only when it runs top to bottom from a clean kernel.
5. Charts land in `analysis/output/` (gitignored).

To run one for another team without editing it, run it from a clean kernel with
parameters (the saved notebook is not changed):

```powershell
analysis/.venv/Scripts/python analysis/tools/run_notebook.py analysis/week01-save-the-season.ipynb --param TEAM=PHI
```

Any name assigned in the cell tagged `parameters` can be set this way.

Before committing a notebook, clear its outputs (**Edit > Clear Outputs of All
Cells**, then save) and run the check:

```powershell
analysis/.venv/Scripts/python analysis/tools/check_notebooks.py
```

It fails if any notebook still has outputs or anything that looks like a
connection string or key.

## Make a thumbnail

Export the chart first (the thumbnail embeds it), then:

```powershell
analysis/.venv/Scripts/python analysis/thumbnails/make_thumbnail.py --config analysis/thumbnails/configs/sample.json
```

Add `--formats youtube` (or `vertical`, `feed`, comma-separated) to render only
some sizes. PNGs land in `analysis/output/thumbnails/<name>-<format>.png`.
Notebooks build the config and call `render()` in section 7, so this command is
for redoing one by hand.

### Config fields

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
| `headline` | yes | 3 to 5 words, shown uppercase, 2 lines at most (it shrinks to fit, and fails if it cannot) |
| `chart` | yes | A PNG file name in `analysis/output/` |
| `sport` | yes | `nfl`, `nba` or `tennis`; sets the small tag |
| `subline` | no | Up to 60 characters |
| `callout` | no | `value` up to 8 characters, `label` up to 40 |
| `background` | no | An image path relative to the config file, shown under a dark overlay; otherwise a dark gradient |
| `name` | no | Lowercase slug for the file names; defaults to the config file name |

Unknown fields are an error, so a typo never gets silently ignored. Keep
configs in `thumbnails/configs/` and commit them, so any thumbnail can be
rebuilt.

**No team logos or player photos**, in a background or anywhere else. The
generator cannot check what an image shows; that part is on me.

### Sizes and safe zones

| Format | Size | Kept clear | Why |
|---|---|---|---|
| `youtube` | 1280x720 | the bottom-right 240x110 | Video length badge |
| `vertical` | 1080x1920 | top 240, bottom 420, right 140 | TikTok and Reels UI; profile grids crop covers to 3:4 |
| `feed` | 1080x1350 | 80 at each side | The Instagram grid crops 4:5 posts to 3:4 |

### Change the look

The design is `thumbnails/template.html` (structure) and
`thumbnails/template.css` (everything visual: sizes, spacing, gradient, each
format's layout). Open `template.html` in a browser to see it while editing,
then rerun the command. Brand colors come from `lib/style.py`, so change them
there. Rendering is offline: fonts load from `fonts/`, and any web request is
blocked and reported.

## Tests

```powershell
analysis/.venv/Scripts/python -m pytest analysis/tests
```

These run separately from the app's Verify command, so CI never installs the
notebook packages.

## Folder map

| Path | What it holds |
|---|---|
| `lib/db.py` | `read_engine()`: the one read-only database connection |
| `lib/style.py` | The one chart style: brand colors, fonts, sizes, title, source line, credit |
| `lib/nfl_queries.py` | Read-only NFL queries: regular-season games, team efficiency, giveaways |
| `lib/nfl_team_report.py` | Save the Season numbers: record and luck, ranks, ratings, simulation, playoff bar, verdict |
| `lib/nflverse.py` | Free nflverse files, cached in `data/`; the only place `nfl_data_py` is used |
| `lib/team_posts.py` | Draft posts for a Save the Season team, under the language rules |
| `lib/glossary.md` | Plain-language definitions of every stat used so far |
| `templates/notebook-template.ipynb` | Copy this to start a new week |
| `tools/check_notebooks.py` | Pre-commit check for outputs and secrets |
| `tools/run_notebook.py` | Runs a notebook on a clean kernel with `--param NAME=value` |
| `week01-save-the-season.ipynb` | Week 1: can a 2-4 team still save its season? (run for DAL and PHI) |
| `fonts/` | Bundled Barlow Condensed, DM Sans and JetBrains Mono (OFL) |
| `thumbnails/logo.png` | The logo; its blue `#09BDFE` is the one accent color |
| `output/` | Exported PNGs (gitignored) |
| `data/` | Cached public data files (gitignored) |

## Notebook template

Every notebook follows this order:

1. **The question** in one sentence.
2. **The concept** this week teaches, explained for a beginner in 3 to 5
   sentences.
3. **Data:** where it comes from, which seasons and weeks, how many games or
   plays.
4. **Method** in plain English.
5. **Analysis.**
6. **The answer** in one sentence, with the main caveat.
7. **Chart export** (both sizes) and a thumbnail config and render.
8. **Draft posts** (one analysis makes three posts a week):
   - Main video: a 45 to 60 second script (hook in the first sentence, written
     for voiceover over the chart) plus on-screen caption text.
   - Chart post: a short X/Threads caption and a longer LinkedIn version (150 to
     250 words, first person, ends with what I learned).
   - Follow-up clip: a 15 to 20 second script on the single most surprising fact
     from the analysis, for later in the week.
9. **What I learned:** 3 bullets on the concept and the method, and any new
   terms added to `lib/glossary.md`.

## Language rules

These apply to every chart, script and caption.

- Write for a sports fan who has never heard of analytics.
- Lead with the answer, then the why.
- Translate every stat into plain words. If a real term is used (EPA, true
  shooting %), define it once in under 10 words.
- Turn numbers into real things: "about 1 extra win a season", "1 in 5".
- One chart, one point. Gray out everything except what the point is about. The
  chart title states the answer.
- Be honest about luck and small samples, in plain words.
- No betting advice, no picks, no claims the data does not support.

## Chart rules

- Two sizes: **feed** 1080x1350 and **vertical** 1080x1920.
- The title states the answer; the logo blue marks the one thing the point is
  about, and everything else is gray.
- Every chart has a source line ("Source: ... data through week N") and the
  logo plus @numbersbehindthegame.
- Text is large enough to read on a phone. In the vertical size, content stays
  clear of the top and bottom bands that TikTok and Reels cover.

## Roadmap

A 12-week concept plan. Week 1 is built (`week01-save-the-season.ipynb`); the rest are planned.

| Week | Concept | Question |
|---|---|---|
| 1 | Luck vs skill | Point differential vs record (Save the Season #1, Real or Lucky? #1) |
| 2 | Sample size | How many games until a stat means something |
| 3 | Rates beat totals | NBA scoring leaders, per 36 minutes and per 100 possessions |
| 4 | Expected value | NFL 4th-down calls (Coach's decision of the week) |
| 5 | Win probability | Biggest swings of the Thanksgiving NFL games |
| 6 | Simulation | Should an NBA team foul up 3? |
| 7 | Correlation vs causation | Does running the ball win NFL games? |
| 8 | Context | Opponent-adjusted point differential: which records are fake |
| 9 | True shooting % | Who really scores efficiently |
| 10 | Shot value | Is the NBA midrange dead? |
| 11 | Elo | Tennis Elo vs official rankings |
| 12 | Putting it together | NFL playoff teams by the numbers |

### Recurring series

These rotate around the weekly concept video.

- **Real or Lucky?** Is a hot or struggling team's record real, or luck?
- **Line Breakdown.** Why a player prop or team total is set where it is.
  Explain the line, never pick a side. Always say "not betting advice". No
  "lock" or "guaranteed" language, and no sportsbook links.
- **Save the Season (NFL).** What is broken on a struggling team, and can they
  recover?

### Optional tennis posts

Tennis is event-driven, not weekly. Confirm every date before posting.

| When | Event | Idea |
|---|---|---|
| Week 2 | Paris Masters (Nov 2 to 8) | Players outperforming their ranking |
| Weeks 2 to 3 | WTA Finals (Nov 8 to 15) | Top 8 women, Elo vs official ranking |
| Week 4 | ATP Finals (Nov 15 to 22) | Who should be the favorite, by the numbers |
| December | Off-season | Evergreen: serve on clay vs grass; does winning the first set predict the match |
| Weeks 11 to 12 | Australian Open build-up | Opening week Jan 11 to 16, main draw Jan 17 to 31 |
