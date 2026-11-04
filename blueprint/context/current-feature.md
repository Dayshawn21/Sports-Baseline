# NHL PrizePicks lines: three day-of pulls before puck drop

**Type:** Fix
**Branch:** `fix/nhl-prop-lines-schedule` (not yet created)

## The problem

On 2026-11-04 `/nhl/board` and `GET /nhl/props?date=2026-11-04` held 4 of 12
markets (shots on goal, points, assists, goals; 293 lines). Power Play Points,
Blocked Shots, Plus/Minus, Goalie Saves, Hits, Time On Ice, Goals Allowed and
Faceoffs Won showed 0. Nov 1, 2 and 3 had all 12, so ingest and the market map
in `api/app/nhl/markets.py` work. PrizePicks posts the secondary markets on
game day, and the day-of pull was missing: the 17:15 UTC slot had not fired by
21:26 UTC. A manual `workflow_dispatch` at 21:27 UTC then stored all 12
markets (832 lines).

`nhl-prop-lines.yml` has two crons, `15 17` and `45 22` UTC. Recent scheduled
runs started at (UTC): Nov 4 02:42, Nov 3 22:19, Nov 3 03:42, Nov 2 23:53,
Nov 2 01:48, Nov 1 21:12, Nov 1 01:27, Oct 31 20:27. None is near 17:15 or
22:45, and several nominal slots left no run at all. GitHub documents that
scheduled runs can be delayed under load, especially at busy times, and may be
dropped. So a day with only two nominal slots can end with zero day-of pulls.

Earliest puck drops are about 00:00 UTC (7 pm ET); weekend matinees can be
around 17:30 UTC. The secondary markets must be stored before then.

## Options weighed

| Option | Verdict |
|---|---|
| Move the first slot earlier, keep two | Does not fix a skipped or very late slot; still one miss from an empty board |
| Add a third slot, spread across the day (recommended) | Three independent chances before 00:00 UTC; a single delay or drop no longer empties the board |
| Four or more slots | Little extra protection, more PrizePicks traffic and more rate-limit (exit 75) exposure |
| Cron at `:00`/`:30` | Rejected: top-of-hour is the most congested time, and NFL pulls sit on `:00` |
| Retry or self-reschedule inside the job | Out of scope: a job that never starts cannot retry |

PrizePicks cost: each run is one public-feed snapshot with no credits, and the
ingest already honors 429 Retry-After and exits 75. Going from 2 to 3 runs a
day adds one request per day for NHL. Neighbouring slots to stay clear of
(UTC): NBA props `16:30`, `22:15`; NFL props `:00` on game days; tennis props
`13:00`; `nhl-odds.yml` `:40` every 3 hours (21:40 is the nearest); `nhl-context.yml`
`:17` hourly.

## The fix (recommended)

Replace the two crons with three, all off-minute and months unchanged
(`1-6,9-12`):

- `37 14` : morning pull, catches matinee boards and the first day-of posts.
- `22 18` : midday pull, the main window for secondary markets.
- `27 21` : last pull, about 2.5 hours of cushion before a 00:00 UTC puck drop
  so one delay of an hour or two still lands before it.

Update the header comment to say why (three slots, delay cushion, no slot near
NBA/NFL/`nhl-odds` minutes). Update the schedule sentence in `docs/commands.md`
(the NHL props bullet, now "17:15 and 22:45 UTC"). No change to the job
steps, `prizepicks_nhl.py`, markets, models or any other workflow.

If the owner wants a different spacing, only the three cron lines change.

## Build steps

- [ ] **Step 1 - schedule and comment.** Edit the `schedule:` block and header
  comment in `.github/workflows/nhl-prop-lines.yml`. Done when: the file has
  exactly three crons (`37 14`, `22 18`, `27 21`, each `* 1-6,9-12 *`),
  `workflow_dispatch` and the job steps are unchanged, `git diff` touches only
  that file, and no em dash appears.
- [ ] **Step 2 - docs.** Update the schedule sentence in `docs/commands.md`
  (NHL props bullet) to the three times. Done when: no mention of
  "17:15 and 22:45" remains in `docs/`
  (`grep -rn "22:45" docs`) and the bullet matches the workflow.
- [ ] **Step 3 - local checks.** Done when: the workflow parses as YAML
  (`python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/nhl-prop-lines.yml'))"`
  from `api/` venv) and `npm --prefix web run verify && cd api && python -m pytest`
  passes (no code changed, so this is a regression guard only).

## What can and cannot be verified

- **Locally:** YAML validity, cron syntax, the diff scope, Verify.
- **Not locally:** that GitHub registers the new schedule and fires it on time.
  Per AGENTS.md a workflow registers only when a push changes its file, and
  delays are GitHub's. This stays unproven until the change is pushed and runs.
- **Needs a separate yes in chat each time:** the push, the merge, and any
  `workflow_dispatch` (it calls PrizePicks and writes to the shared Neon
  database). None happens during `/implement`.

## Post-merge verification plan (done-when)

After an approved push, wait 3 to 4 game days, then:

1. `gh run list --workflow nhl-prop-lines.yml --limit 20 --json createdAt,event,conclusion`:
   each day shows scheduled runs from all three slots (or at least two), each
   starting before 00:00 UTC on game days, none failing with exit 75.
2. For each of those days, a per-market count of
   `GET /nhl/props?date=YYYY-MM-DD` (as of about 22:00 UTC): all 12 markets
   above zero on a day with games. Today's 4-of-12 is the failing baseline.
3. If a slot still starts 3+ hours late on several days, revisit with the
   evidence (consider a fourth slot or a different provider-side check); that
   would be a new spec.

## Out of scope

NHL Python code, market mapping, models, other sports' workflows,
`nhl-ingest.yml` (its `--relink` is unchanged), a retry or alerting layer.
Coordinate nothing with `nhl-56c-spec`: no overlap in files.
