# TennisMyLife ELO identity registry

Reviewed inputs for `python -m app.ingest.tennis_elo` (build-plan 41b, Step 4b).
They normalize provider identities before deduplication, replay and local
mapping. They never modify `players`, `player_aliases`, `player_elo` or any
match link.

**Status:** all 60 aliases and 9 local overrides are verified and applied by
the ingest. On 2026-10-20 the owner delegated the remaining seven decisions
("Do what you think is best"). The six local overrides follow the established
rule; Ilagan now has independent official result corroboration (below).
This review does not approve a database write.

## Files

- `tennis_elo_identities.csv` maps a raw `(namespace, raw_provider_id)` to a
  `canonical_provider_id` in the same namespace. An ID absent from the file is
  its own canonical key. Canonical keys never cross ATP/WTA.
- `tennis_elo_local_overrides.csv` pins a canonical provider identity to one
  local `players.id` when its provider names resolve to several local rows.

`status` is `verified` or `proposed`. Only `verified` rows may be applied; a
`proposed` row stays blocking until the owner decides it.

## Canonical key rule

Within a group, the canonical ID is the one with the most admitted matches in
the audited manifest, ties broken by earliest provider date, then the ID
string. It is a stable label, not a claim that one ID scheme is "correct".

## What the audit found

Audited manifest `8ce25f5b...37a7` (27 files, 71,346 unique admitted matches,
2,755 provider identities), including every untracked opponent.

- **WTA renumbering.** In 2026 TennisMyLife began filing some players under
  their WTA-official player IDs (`3xxxxx`) instead of the legacy `2xxxxx` IDs.
  Queen's Club and 's-Hertogenbosch 2026 use official IDs for every player;
  about fifteen other 2026 events mix in a few. 73 official IDs appear; 51
  pair with a legacy ID by exact name, 6 more by spelling-normalized name.
- **Provider ID errors.** WTA `200035` (one Stuttgart 2026 row for Shuai
  Zhang) is officially another player's ID; the row's age, country and the
  independent local livetennis match confirm it is Zhang. Three US Open 2026
  rows (Quevedo, Stoiana, Brantmeier) use one-off IDs.
- **ATP.** Two spelling/ID forks: Hernandez-Aguila (`A0JF`, `H811`) and
  Ilagan (`I0A0`, `I0B0`).

## Evidence standard

The standard provider-alias evidence requires all of these:

1. Same normalized name, or the same name after removing spaces, hyphens and
   token order, in the same namespace.
2. Birth dates implied by the provider's own `*_age` column and
   `tourney_date` agree within 2 days. Observed spread: 0 or 1 day for all 59.
3. Same country, allowing a recorded nationality switch with an identical
   birth date (Kasatkina RUS/AUS, Rakhimova and Kudermetova RUS/UZB, Quevedo
   USA/ESP) or a missing country.
4. The IDs never appear in the same event and never play each other, so a
   merge cannot create a self-match.

Ilagan is a documented exception to the age requirement: both raw-ID results
are corroborated by the official tournament draw, with ATP's indexed result
identifying the canonical ID. Local overrides use the separate rule below;
known local birth-date discrepancies remain recorded and unmodified.

Spot checks against official WTA profiles (checked 2026-10-20) matched the
implied birth date for 324166 Rybakina, 318711 Sherif, 311779 Zhang, 329512
Brantmeier, 321157 Burillo, 323119 Bulgaru, 327252 Ku, 322417 Ma, 330970
Rakotomanga Rajaonah and 313169 Begu.

ATP profile pages are not evidence: they render whatever name the URL slug
carries, for any ID.

## Not merged

- **ATP `C0KH` / `P0IL` (Julio Cesar Porras).** Different countries (ARG,
  ESP), no age data. Kept as two identities; neither maps to a local player.
- **18 official WTA IDs with no legacy partner** (for example Yihan Qu,
  Kristina Liutova). No same-person candidate; they stay standalone.
- **Name-token false positives** such as Elena Micic and Elena Rybakina,
  Vivian Wolff and Vivian Yang, Jana and Alena Kovackova.

## Final seven decisions (2026-10-20)

- **ATP `I0A0` to `I0B0` (Andre Ilagan).** Same name and country (USA); the
  two Washington qualifying matches (2026-07-27) fall in a gap in `I0B0`'s
  schedule. No age data on `I0A0`. The [official Washington qualifying draw](https://www.protennislive.com/posting/2026/418/qs.pdf)
  confirms both cached results: Ilagan beat Bertola 7-5 7-6(2), then lost to
  Giron 6-3 7-6(2). [ATP's indexed Washington results](https://www.atptour.com/en/scores/current/washington/418/results?gsid=f2c28d95-f94e-4817-bf2e-1d90e1f80dee)
  identify Ilagan as `i0b0` in the Bertola result. The live ATP page returned
  403; the indexed result and accessible official PDF were checked on
  2026-10-20. Accepted on this result-level evidence, not a profile URL slug.
- **Six local overrides for the spelling-fork merges** (Begu, Burillo,
  Bulgaru, Ma, Ku, Rakotomanga Rajaonah). Merging their provider IDs joins
  two name variants, and each variant resolves to a different local row.
  Each override targets the row with the `livetennis_id` and most local
  matches, the same rule as the approved overrides. Found by the first
  normalized dry run, after the registry draft was reviewed.

## Local overrides

Each override targets the local row that carries the `livetennis_id`, so the
candidate rating lands on the player that upcoming matches link to. The other
local rows keep their data and simply receive no candidate snapshot.

| Provider | Local rows | Target | Why |
|---|---|---|---|
| ATP `D0LJ` Diego Dedura(-Palomero) | 138604, 419, 17602 | 138604 | livetennis 330, latest matches, birth date 2008-03-12 vs implied 2008-03-13 |
| WTA `213873` Gabriela (Andrea) Knutson | 2503, 53141 | 53141 | livetennis 805, all local matches; its stored birth date (1989) disagrees with the provider's (1997), recorded, not corrected |
| WTA `216133` Xinyu / Xin Yu Wang | 2153, 9331 | 9331 | livetennis 791, all local matches, birth date exact |
| WTA `201593` Irina-Camelia Begu | 2147, 65719 | 65719 | livetennis 987, all local matches; local birth dates disagree with provider/profile, recorded in CSV |
| WTA `213706` Irene Burillo | 2664, 32240 | 2664 | livetennis 241, 40 of 45 matches and latest; local birth date discrepancy recorded |
| WTA `214480` Miriam Bulgaru | 2556, 91667 | 2556 | livetennis 1577, 39 of 40 matches; local birth date discrepancy recorded |
| WTA `215946` Yexin Ma | 2547, 74631 | 74631 | livetennis 1099, all local matches, birth date exact |
| WTA `220454` Yeonwoo Ku | 2507, 92193 | 92193 | livetennis 1589, all local matches, birth date exact |
| WTA `239456` Tiantsoa Rakotomanga Rajaonah | 2370, 9335 | 2370 | livetennis 281, 30 of 39 matches and latest; local birth date discrepancy recorded |

## Changing this registry

Before activation, any edit invalidates an uncommitted reviewed manifest. After
activation, a change needs a new normalization version and a separate
experiment review. New conflicts found by a daily dry run block the write
until reviewed here.

## Shadow experiment pins

`tennis_elo_experiment.json` pins the identity registry, frozen coefficients,
reliability/staleness gates and incumbent model versions for
`python -m app.ingest.tennis_elo_comparison --dry-run`.

`activated_at: null` means inactive. Preview counts can show available pairs,
but none are forward observations and `--write` refuses to activate the
experiment. Activation requires a separate reviewed timestamp. Its first
eligible date is the next full UTC day after activation and spec approval;
a complete candidate snapshot from that day is required before freezing.
The config hash is copied into pairs and coverage attempts, so later pin
changes stop accrual even when the previous cycle had only missing-source
skips. Never update this file automatically to match a changed runtime.

### Experiment history

| Experiment | Identity version | Status |
|---|---|---|
| `tennis-elo-source-v1` | `tennis-elo-identities-v1` | Closed 2026-10-29, stopped with no verdict. Activated 2026-10-21; the WTA alias fix (`e4fe60b7`) changed the registry and stopped accrual on 2026-10-28. Its 52 pairs and 6 freeze cycles stay stored unchanged and are never pooled with v2 or scored. |
| `tennis-elo-source-v2` | `tennis-elo-identities-v2` | Pinned 2026-10-29 under the same pre-registered rule. Coefficient, gate and incumbent pins are unchanged from v1. Activated 2026-10-29T20:00:36Z; first eligible UTC day 2026-10-30. |

The next post-activation registry change closes v2 the same way. Batch
reviewed alias fixes to avoid repeated restarts.

## Scheduled handoff and recovery

The 11:00 UTC TennisMyLife workflow starts an isolated candidate refresh after
the existing box-score job succeeds. The 13:30 UTC prediction workflow starts
the shadow job after predictions and existing prop snapshots succeed. The
`tennis-elo` and `tennis-elo-comparison` dispatch choices run just the selected
new job. Each has its own non-cancelling concurrency group; database locks and
immutable daily/cycle contracts also protect local and runner retries.

The jobs restore exactly the same UTC-day, implementation and identity-keyed
Actions cache containing `files/` and `manifests/`. Refresh shares the cache
only after `--check-snapshot` verifies the entire stored roster and original
source-file hashes. No previous-day cache is accepted. A cache is disposable:
if today's database roster already exists but its originals are unavailable,
refresh cannot recreate them by downloading changed upstream files. Its cache
validation fails, and an active shadow cycle records eligible coverage attempts
but freezes no pairs. A new daily refresh can recover the next UTC day. Keep
the original local cache with the review evidence for manual recovery.

`--scheduled` performs no database work while inactive or before the first
full eligible UTC day. Explicit `--write` continues to reject those states.
Missing/invalid daily inputs never fall back to a different ELO source.

## Once-only report artifacts

`python -m app.backtest.tennis_elo --count` is the safe default. No workflow
runs `--score`. A separately approved `--score --group ATP`, `WTA` or
`ATP_CHALLENGER` locks the sample before calculating losses. Preserve the
whole `api/data/tennismylife-elo/reports/` directory with experiment evidence
and copy it before moving report execution to another machine. File locks
protect concurrent local invocations; they do not coordinate independent
machines. Never score the same experiment/group independently on a fresh
runner or delete its artifacts to obtain another result.

## Approved activation

Owner approved Step 7 and continuing shadow activation. Activation is recorded
at `2026-10-21T02:25:51.864941+00:00`. The first eligible full UTC day is
`2026-10-22`; the config SHA-256 is
`bdab3a645c923bef5742a1ff179504a342462afe7f023d6319ccc8814633e2a5`. No earlier case can enter.
The first real freeze and GitHub runner acceptance remain pending. This
activation does not switch the served ELO source or authorize scoring.
