# 42c Step 1: ESPN feed verification and parser

## Observed source

Read on 2026-10-21 from the public keyless
[NBA injuries feed](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries).
The sandbox network attempt failed; the subsequent approved network read
succeeded. No database was accessed or changed.

| Observation | Value |
|---|---|
| Root `status` | `success` |
| Root `timestamp` | `2026-10-21T17:52:32Z` |
| Root `season` | year 2027, type 2, displayName 2026-27 |
| Team groups | 28 |
| Injury entries | 80 |
| Status counts | 52 Out, 28 Day-To-Day |
| Report/current-athlete team disagreements | 1 |
| Pure parser on the captured full response | 80 entries, 1 team mismatch |

The root is an object with `timestamp`, `status`, `season` and `injuries`.
`injuries` is an array of team groups with `id`, `displayName` and an
`injuries` array. Each injury has `status`, `date`, `shortComment`, `details`
and `athlete`, among other unused fields.

| Internal field | Verified payload path |
|---|---|
| Reported team ID | `injuries[].id` |
| Athlete ID | `injuries[].injuries[].athlete.links[].href`, NBA player `/id/<id>` path |
| Player name | `athlete.displayName` |
| Current athlete team | `athlete.team.id` and `.abbreviation` |
| Provider status | injury `status`, not athlete `status` (which may say Active) |
| Provider update time | injury `date`, aware ISO time |
| Body/injury detail | `details.side`, `.type`, `.detail`, plus `shortComment` |
| Expected return text | `details.returnDate` |

Athlete `id` was absent in the observed entries, so player links are necessary.
The parser also supports an explicit positive athlete ID if supplied later;
conflicting explicit/link identities fail the snapshot. Only ESPN NBA player
HTTP(S) links are identity sources; display names never match players.

All 30 team ID/code mappings were verified separately against the public
[NBA team directory](https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams).
New Orleans (3/NO) and New York (18/NY) were absent from this injury response.
No all-30-groups assumption is valid. The endpoint supplied no pagination or
total-entry-count field, so structural validation cannot establish whether ESPN
itself omitted a report. UI wording remains "reported by ESPN", never healthy
or authoritative availability.

## Identity discrepancy

The report group for LA Clippers (12/LAC) contained Brandon Ingram, athlete
3913176, with nested athlete team Toronto (28/TOR), status Out, updated
`2026-09-28T18:01Z`. Both IDs are retained. This entry must not silently move
to Toronto's report or attach to a player prop while the team identities
disagree. A team list must identify the provider mismatch explicitly.

This is observed provider inconsistency, not proof of a real player injury,
transaction or availability. No such independent claim is made.

## Fixture and failure behavior

`api/tests/fixtures/espn_nba_injuries.json` is a reduced three-entry capture:
Out, Day-To-Day and the team disagreement. IDs, names, dates, status, links and
structured details preserve the observed values. Narrative comments were
replaced with a short synthetic string; unused links, biographies and news were
removed. The complete original response remains temporary, outside tracked
files. The test suite performs no network calls.

`parse_injury_feed` returns immutable typed records. It requires success, an
aware root timestamp, an explicit root injuries array, known team groups and
valid required player identity/name/status. Missing optional values stay null,
unknown nonempty status text stays visible, identical duplicate entries
collapse and conflicting duplicates fail the whole parse. A malformed group
or entry cannot masquerade as successful emptiness. Explicit successful empty
arrays are supported by synthetic fixtures; an empty live league response was
not observed.

The parser performs no writes or logging; the later ingest step owns atomic
storage and failure reporting. Provider timestamps remain distinct from the
later ingest fetch timestamp. Neither this parser nor this probe modifies any
projection, probability or freeze code.

## Verification

- `.venv\Scripts\python.exe -m pytest tests/test_nba_injuries.py -q` from
  `api/`: 49 passed.
- Pure parser against the complete temporary live capture: 28 groups, 80
  parsed entries, one preserved mismatch.
- Full Verify passed using `api\.venv\Scripts\activate.bat` followed by
  `npm --prefix web run verify && cd api && python -m pytest`: web typecheck,
  659 web tests, production build, and 3,519 API tests (including 49 new tests).
  The first sandbox attempt reached web verification but esbuild could not
  read the Vite configuration because of filesystem restrictions; the approved
  rerun succeeded. Existing large-bundle and Starlette/AnyIO deprecation
  warnings remain.

No workflow, schema migration, UI or deployment exists for 42c yet. Step 1 is
implemented but remains unchecked until user review approval.
