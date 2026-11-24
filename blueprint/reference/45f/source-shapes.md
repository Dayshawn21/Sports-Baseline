# ESPN NHL context source verification

Verified October 24, 2026 using three bounded keyless JSON requests. No database
access, snapshots, paid odds requests or model operations were performed.
Raw local responses are ignored artifacts in `output/45f-source-probe/`.

| Source | Observed contract |
|---|---|
| [Injuries](https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries) | Root timestamp, success status, season and team-grouped injuries. Athlete ID is present in ESPN NHL player links; injury row ID is a different identity. |
| [Dated scoreboard](https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=20261024&limit=100) | 12 events; root leagues/events/provider, without root day or timestamp. Probable status is an object containing name Expected/Confirmed and type expected/confirmed. |
| [Team directory](https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams?limit=100) | 32 teams with ESPN IDs and source abbreviations; retained as a minimal fixture. |

ESPN aliases: LA to LAK, NJ to NJD, SJ to SJS, TB to TBL, UTAH to UTA.
SEA uses ESPN team ID 124292; Utah uses 129764. Existing shared NHL prop
normalization stays unchanged; ESPN context uses its own explicit aliases.

The injury feed's timestamp was `2026-10-24T16:18:22Z`. The injury fixture keeps
one example for each observed status (Injured Reserve, Day-To-Day, Out), retains
identity/date/details fields and replaces commentary with a short synthetic
comment. Names, source IDs and team mappings are provenance, not internal links.
Tests separately construct unknown status, missing optional fields, duplicates
and team-disagreement cases; they are not claimed as live feed observations.
The pure parser also accepted the entire saved live response: 135 entries
across 29 teams, with zero nested team disagreements. This is source-shape
acceptance only, not database linking, API or deployment acceptance.

The injury feed supplies no advertised total or pagination metadata. A parser
can reject malformed responses but cannot prove ESPN omitted no real-world
injuries. Empty success means only no injuries reported by ESPN. Scoreboard
date/coverage and truncation validation belong to Step 1b.

Step 1a has no ingest command, schema change, API or UI integration and does
not establish that any particular NHL player has been linked successfully.

Step 1a verification passed: 67 focused tests and the exact root Verify command
with the API venv on PATH (`npm --prefix web run verify && cd api && python -m pytest`).
Web typecheck, 878 web tests, production build and 4,240 API tests passed.
Existing Vite bundle-size and Starlette deprecation warnings remain.

## Step 1b: goalies and matching

The goalie fixture retains the first two events from the same saved October 24
response, including nested status objects, source athlete/team IDs and source
positions. The complete saved response parses to 24 team observations: 11
Confirmed and 13 Expected, with no nested athlete-team disagreements. This is
parsing acceptance only. Internal matching is verified with controlled typed
candidates; no database roster or live internal IDs were read.

- No root date or timestamp is supplied. Source timestamp remains null. Scope
  date comes from the caller's dated request; every event is validated against
  that Eastern date, including UTC starts after midnight.
- Reaching the requested response limit is treated as potentially truncated.
  Silent upstream omissions cannot be proven or detected without another
  independent source. An empty response's date is request provenance only.
- Source `timeValid=false` preserves the scheduled timestamp but prevents game
  linking. Explicit preseason events are excluded; unknown season types fail.
- Missing probables create not_reported competitor observations. Unknown names
  or conflicting status name/type pairs remain unknown and never become Confirmed.
- Injury/goalie wrappers enforce source team disagreements. Player candidates
  must be NHL, exact full name after conservative punctuation/accent folding,
  and the same canonical team. Goalie candidates must have position G. Initial,
  fuzzy, missing-team and ambiguous matches stay unresolved.
- Event candidates require NHL REG/PST, ordered away/home teams and one aware
  start within 60 minutes inclusive. Multiple candidates are ambiguous even
  when one is closer. ESPN event IDs are retained separately from internal IDs.

The 163-test focused suite covers injury, goalie and matching logic. Empty,
unknown, malformed, conflicting, ambiguous, postponed-time and cross-sport cases
are fixture mutations, not claims about actual source records. Storage, real
ingest, API and browser acceptance remain later steps.

Step 1b final gate passed with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
Web typecheck, 878 web tests, production build and 4,336 API tests passed.
`git diff --check` passed; existing bundle-size/deprecation warnings remain.
Review diff relative to Step 1a is local `output/45f-step1b.diff`.
