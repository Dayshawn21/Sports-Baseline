# Recover H2H when provider names are ambiguous

**Type:** Fix

## The problem

The prediction modal hides its H2H strip for Maria Timofeeva vs Ann Li even
though they have played four completed matches. The UI is behaving as designed:
it hides the strip when both H2H win counts are zero. The bad state originates
in the ingest path.

For live match `39537`, the API returns `h2hP1Wins: 0` and `h2hP2Wins: 0`, and
the database has no overall H2H row for player IDs `2348` and `2105`. Both
players are correctly resolved and have stable Live Tennis roster IDs (`540`
and `649`), so this is not another player-linking failure.

A focused provider request to `/h2h?p1=Maria Timofeeva&p2=Ann Li` returns HTTP
400 with `error: ambiguous_name`. The provider treats both values as name
fragments, and `Ann Li` also matches names such as `Carolyn Ann Lim Hui` and
`Kerry Ann Lim`. In `api/app/ingest/livetennis.py`, `fetch_h2h` treats every 400
as unresolvable and returns `None`. `write_to_db` then skips the H2H write, the
predictor defaults the missing counts to zero, and the UI hides the section.

The same provider exposes completed match history from January 2023 onward via
`/history/matches`. That endpoint accepts stable roster player IDs, so it can
resolve this case without guessing from names or adding a second data source.

## The fix

Keep `/h2h` as the primary path. Only when its response is specifically an
`ambiguous_name` 400 and both Live Tennis roster IDs are available, query
`/history/matches` for one player ID and aggregate rows whose two embedded
player IDs exactly match the requested pair.

Add a pure history-to-H2H mapper that:

- orients every win to the requested player 1 and player 2 IDs, even when the
  provider returns them in the opposite order
- counts only completed pair matches with a winner of 1 or 2
- builds the same overall and Hard, Clay, and Grass shape returned by
  `parse_h2h`
- ignores other opponents, doubles, unknown surfaces for the surface split,
  malformed rows, and matches without a winner
- returns `None` when no qualifying completed meetings exist

The fallback must remain narrow and quota-conscious: run it only for a confirmed
`ambiguous_name`, filter by one stable player ID, request singles history from
the endpoint's January 2023 coverage boundary, and use the existing bounded
pagination helper. Pass both provider IDs from each normalized match through
`write_to_db` into `fetch_h2h`.

Must not break:

- successful `/h2h` responses, which remain authoritative and make no history
  request
- genuine zero-meeting pairs, which must remain absent rather than storing a
  fabricated 0-0 row
- other HTTP 400 responses, authentication errors, and tier blocks, which must
  not trigger a history scan
- H2H player orientation when the database stores the pair in canonical ID
  order
- existing match, prediction, and modal response shapes

Do not hardcode the Timofeeva/Li names, IDs, or 0-4 result. No database schema,
predictor, or UI change is needed.

## Build steps

### Step 1 - map exact player history into H2H totals  [x] DONE

In `api/app/ingest/livetennis.py`, add a pure mapper that accepts history rows
and the requested provider player IDs, filters to that exact singles pairing,
and returns the existing H2H result shape.

Add focused tests in `api/tests/test_livetennis_parsers.py` covering reversed
player order, multiple surfaces, unrelated opponents, unknown surfaces,
malformed or undecided matches, and no qualifying meetings.

**Done when:** the new mapper tests pass and demonstrate that counts always stay
oriented to the requested IDs without any network or database access.

### Step 2 - use ID-based history only for ambiguous names  [x] DONE

Teach `fetch_h2h` to identify the provider's `ambiguous_name` error from
`FatalStatus.body`. When both provider IDs exist, fetch the bounded singles
history for one ID and pass it through the mapper. Update `write_to_db` to supply
the two IDs already present on each normalized match.

Add async request-path tests showing that:

- a successful direct H2H response performs no history request
- `ambiguous_name` with both IDs uses history and returns exact-pair totals
- `ambiguous_name` without IDs returns `None` without scanning history
- a different 400 does not use the fallback
- a tier block still propagates so the ingest can stop H2H work for the run

**Done when:** the API tests pass; a focused provider check, performed only after
explicit approval because it consumes quota, returns `(0, 4)` for Live Tennis
IDs `540` and `649`; and an explicitly approved one-pair production backfill
causes `/tennis/predictions/today` to return `h2hP1Wins: 0` and `h2hP2Wins: 4`
for match `39537`, making the H2H strip visible without a UI change.

**Evidence recorded 2026-08-26:** all 218 API tests passed, the web build passed,
and all 31 web tests passed. Mocked request-path tests proved the direct response,
ambiguous fallback, missing-ID, unrelated 400, authentication, and tier-block
branches without network access. After explicit approval, the focused provider
fallback returned overall 0-4, Hard 0-3, and Clay 0-1 for provider IDs `540` and
`649`. After separate approval, those three rows were backfilled through
`upsert_h2h`; repository reads returned the same orientation and values. The
running `/tennis/predictions/today` endpoint returned `h2hP1Wins: 0` and
`h2hP2Wins: 4` for match `39537`, and the user confirmed the H2H strip was
visible after refresh. No API restart was required and all temporary verification
files were removed.

## Verify

1. Run `cd api && .venv/Scripts/python.exe -m pytest -q`.
2. Confirm the new tests cover both direct `/h2h` and ambiguous-name fallback
   paths without making live provider requests.
3. With separate approval for quota use, run one focused fallback request for
   provider IDs `540` and `649` and confirm the computed overall result is 0-4.
4. With separate approval for the live database write, backfill only that pair
   through the existing H2H repository function.
5. Read `/tennis/predictions/today`, open Timofeeva vs Li, and confirm the H2H
   strip shows Li leading 4-0.
6. Confirm a known successful direct-H2H matchup still displays its stored
   totals and did not invoke the fallback.
