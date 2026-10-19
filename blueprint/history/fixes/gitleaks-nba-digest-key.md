# Fix: secret scan flags the NBA digest test's row key

**Type:** Fix
**Status:** complete 2026-10-18
**Branch:** `fix/gitleaks-nba-digest-key`

## Problem

The `secret-scan` job's tracked-tree step failed on the push of `8ab0c7e`
(feature 39a): gitleaks' default `generic-api-key` rule flagged
`key: '21319-7-points'` at `web/src/utils/nbaSlate.test.ts:155`, an NBA digest
row key (`<gameId>-<playerId>-<market>`, entropy 3.52), not a credential. The
line arrived with 38c2 (`0407c4b`), so every push since then has scanned the
same tree; 39a did not touch the file. The commit-range step passed.

## Fix

`.gitleaks.toml` extends the default `generic-api-key` rule with an allowlist
that needs both conditions (`condition = "AND"`): the path is that test file,
and the secret matches `^\d+-\d+-[a-z_]+$`. Any other credential in the file,
and the same value in any other file, is still reported.

Two narrower-looking forms were tried first and rejected:

- A top-level `[[allowlists]]` with `paths` and `regexes` skipped the whole
  file: a planted real-looking `api_key` in it went unreported.
- Adding `targetRules = ["generic-api-key"]` to that block suppressed
  nothing, even with the path or regex alone.

## Evidence

gitleaks 8.28.0 (the workflow's pinned version; Windows build checked against
the release checksums), run on `git archive HEAD` as the job does:

| Config | Tracked tree | Planted file (row key + fake `api_key`) | Same lines in another file |
|---|---|---|---|
| `master` | 1 leak (the row key), exit 1 | both flagged | both flagged |
| this fix | no leaks, exit 0 | fake key flagged, row key skipped | both flagged |

No source or test file changed. The `secret-scan` result on GitHub is
confirmed only after this commit is pushed.
