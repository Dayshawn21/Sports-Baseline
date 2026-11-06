import asyncio
import csv
import json
import random
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.core.tennis_elo import (
    AMENDMENT_COLUMNS, IDENTITY_COLUMNS, OVERRIDE_COLUMNS, IdentityRegistry, TennisEloContractError,
    TennisEloMatch, TennisEloReplay, amendments_sha256, check_amendments, deduplicate, effective_registry,
    IDENTITY_CONTRACT, extends_prefix, normalize_identities, parse_amendments, parse_identity_registry,
    resolve_identity,
)
from app.core.tennismylife import PlayerNameIndex
from app.ingest import tennis_elo as ingest
from tests.helpers.tennis_elo_ingest import INDEX, cached, matches, rows, setup_run  # noqa: F401

BASE = TennisEloMatch(
    namespace="WTA", family="WTA", event_id="2025-1", match_number=1, provider_date=date(2025, 6, 2),
    round="R32", level="500", surface="grass", winner_id="201000", winner_name="Ann Legacy",
    loser_id="202000", loser_name="Bea Other", tournament="Synthetic", score="6-4 6-4", best_of=3,
)


def alias(raw, canonical, namespace="WTA", status="verified"):
    return dict(zip(IDENTITY_COLUMNS, (namespace, raw, canonical, status, "implied birth date spread 0d")))


def override(provider_id, local_id, namespace="ATP", status="verified"):
    return dict(zip(OVERRIDE_COLUMNS, (namespace, provider_id, str(local_id), status, "livetennis-linked row")))


REGISTRY = parse_identity_registry([alias("310000", "201000")], [])


def renumbered_history():
    """The same player under a legacy ID, then an official ID, then the legacy ID again."""
    return [
        BASE,
        replace(BASE, event_id="2026-1111", provider_date=date(2026, 6, 8), winner_id="310000"),
        replace(BASE, event_id="2026-2", provider_date=date(2026, 7, 6), loser_id="201000",
                winner_id="203000", winner_name="Cy Third", loser_name="Ann Legacy"),
    ]


def test_renumbered_ids_share_one_history_under_the_canonical_key():
    replay = TennisEloReplay(normalize_identities(m, REGISTRY) for m in renumbered_history())
    rating = replay.rating(("WTA", "201000"), date(2026, 10, 20))
    assert rating is not None and rating.overall_matches == 3 and rating.grass_matches == 3
    assert replay.rating(("WTA", "310000"), date(2026, 10, 20)) is None
    unnormalized = TennisEloReplay(renumbered_history())
    assert unnormalized.rating(("WTA", "201000"), date(2026, 10, 20)).overall_matches == 2


def test_aliases_never_cross_namespaces():
    atp = replace(BASE, namespace="ATP", family="ATP", winner_id="310000")
    assert normalize_identities(atp, REGISTRY) is atp


def test_unrelated_namesakes_without_a_registry_row_stay_separate():
    namesake = replace(BASE, event_id="2026-3", winner_id="399999", winner_name="Ann Legacy")
    replay = TennisEloReplay(normalize_identities(m, REGISTRY) for m in (BASE, namesake))
    assert {("WTA", "201000"), ("WTA", "399999")} <= set(replay.players)


def test_normalization_that_would_create_a_self_match_is_fatal():
    registry = parse_identity_registry([alias("310000", "201000"), alias("320000", "201000")], [])
    with pytest.raises(TennisEloContractError, match="self-match"):
        normalize_identities(replace(BASE, winner_id="310000", loser_id="320000"), registry)


def test_copies_under_old_and_new_ids_deduplicate_but_conflicting_results_still_stop():
    copy = replace(BASE, winner_id="310000")
    normalized = [normalize_identities(m, REGISTRY) for m in (BASE, copy)]
    assert normalized[0] == normalized[1]
    flipped = replace(BASE, winner_id="202000", loser_id="310000", winner_name="Bea Other", loser_name="Ann Legacy")
    assert deduplicate(normalized) == [BASE]
    with pytest.raises(ValueError, match="Conflicting"):
        deduplicate([normalized[0], normalize_identities(flipped, REGISTRY)])


def test_normalized_replay_is_deterministic_under_shuffling():
    history = renumbered_history()
    expected = TennisEloReplay(normalize_identities(m, REGISTRY) for m in history).rating(
        ("WTA", "201000"), date(2026, 10, 20))
    for seed in range(5):
        shuffled = history[:]
        random.Random(seed).shuffle(shuffled)
        replay = TennisEloReplay(normalize_identities(m, REGISTRY) for m in shuffled)
        assert replay.rating(("WTA", "201000"), date(2026, 10, 20)) == expected


def test_proposed_rows_are_counted_but_never_applied():
    registry = parse_identity_registry([alias("I0A0", "I0B0", "ATP", "proposed")],
                                       [override("D0LJ", 7, status="proposed")])
    assert registry.canonical == {} and registry.local_overrides == {} and registry.proposed == 2


@pytest.mark.parametrize("identities, overrides", [
    ([alias("310000", "201000"), alias("310000", "201001")], []),
    ([alias("310000", "201000"), alias("201000", "200500")], []),
    ([alias("310000", "310000")], []),
    ([alias("310000", "201000", "ITF")], []),
    ([alias("310000", "201000", status="maybe")], []),
    ([dict(alias("310000", "201000"), evidence="")], []),
    ([{"namespace": "WTA", "raw_provider_id": "310000"}], []),
    ([alias("310000", "201000")], [override("310000", 5, "WTA")]),
    ([], [override("D0LJ", 5), override("D0LJ", 6)]),
    ([], [override("D0LJ", 5), override("X0X0", 5)]),
    ([], [override("D0LJ", 0)]),
])
def test_registry_rejects_chains_duplicates_and_malformed_rows(identities, overrides):
    with pytest.raises(TennisEloContractError):
        parse_identity_registry(identities, overrides)


def test_local_override_replaces_name_resolution_but_keeps_the_one_to_one_check(rows):
    first = matches(rows)
    index = PlayerNameIndex({**INDEX.canonical, ("player one", "ATP"): 11, ("p one alt", "ATP"): 33}, {})
    forked = replace(first, winner_name="P One Alt", match_number=20)
    assert ingest.map_players([first, forked], index).conflicts
    pinned = ingest.map_players([first, forked], index, {("ATP", "A001"): 33})
    assert pinned.linked == {("ATP", "A001"): 33, ("ATP", "B002"): 22} and pinned.conflicts == []
    assert ingest.map_players([first], index, {("ATP", "A001"): 22}).conflicts
    missing = ingest.map_players([first], index, {("ATP", "A001"): 999})
    assert ("ATP", "A001") not in missing.linked and "not a local ATP player" in missing.conflicts[0]


def test_collect_matches_normalizes_before_deduplicating_annual_and_ongoing_copies(rows, tmp_path):
    registry = parse_identity_registry([alias("Z999", "A001", "ATP")], [])
    annual = cached(tmp_path, rows[:1])
    renamed = cached(tmp_path, [dict(rows[0], winner_id="Z999")], ingest.SourceFile("ATP", "ongoing_tourneys.csv"))
    results, counts = ingest.collect_matches([annual, renamed], tmp_path, date(2026, 10, 20), registry)
    assert len(results) == 1 and results[0].winner_id == "A001" and counts["ATP"].duplicates == 1


def write_registry(directory, identities, overrides):
    directory.mkdir(parents=True, exist_ok=True)
    for name, columns, data in (("tennis_elo_identities.csv", IDENTITY_COLUMNS, identities),
                                ("tennis_elo_local_overrides.csv", OVERRIDE_COLUMNS, overrides)):
        with (directory / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)


def test_reviewed_manifest_is_pinned_to_the_identity_registry(rows, tmp_path, monkeypatch, capsys):
    registry_dir = tmp_path / "registry"
    write_registry(registry_dir, [alias("Z999", "A001", "ATP")], [])
    writes, _, _ = setup_run(monkeypatch, tmp_path, rows[:1])
    preview = asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir))
    assert "Identity registry tennis-elo-identities-v3" in capsys.readouterr().out
    write_registry(registry_dir, [alias("Z999", "A001", "ATP"), alias("Y888", "B002", "ATP")], [])
    with pytest.raises(ValueError, match="identity registry changed"):
        asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir, dry_run=False,
                               manifest_path=preview.manifest_path))
    assert writes == []


def test_tracked_registry_parses_and_only_verified_rows_apply(tmp_path):
    source = Path(ingest.REGISTRY_DIR)
    loaded = ingest.load_identity_registry(source)
    tracked = {}
    for name in ("tennis_elo_identities.csv", "tennis_elo_local_overrides.csv"):
        with (source / name).open(encoding="utf-8") as handle:
            tracked[name] = list(csv.DictReader(handle))
    verified = {name: [r for r in rows if r["status"] == "verified"] for name, rows in tracked.items()}
    assert len(loaded.registry.canonical) == len(verified["tennis_elo_identities.csv"])
    assert len(loaded.registry.local_overrides) == len(verified["tennis_elo_local_overrides.csv"])
    assert loaded.registry.proposed == sum(len(tracked[n]) - len(verified[n]) for n in tracked)
    shutil.copytree(source, tmp_path / "copy")
    assert ingest.load_identity_registry(tmp_path / "copy").sha256 == loaded.sha256
    assert isinstance(loaded.registry, IdentityRegistry)


@pytest.mark.parametrize("name", ["tennis_elo_identities.csv", "tennis_elo_local_overrides.csv",
                                  "tennis_elo_identity_amendments.csv"])
def test_registry_files_are_checked_out_with_lf_so_every_platform_hashes_the_same_bytes(name):
    assert b"\r" not in (ingest.REGISTRY_DIR / name).read_bytes()


ACTIVATED_ON = date(2026, 11, 6)
AMENDABLE_BASE = parse_identity_registry([alias("310000", "201000")], [override("213873", 53141, "WTA")])


def amendment(provider_id, target, effective_from="2026-11-08", kind="alias", namespace="WTA"):
    return dict(zip(AMENDMENT_COLUMNS, (namespace, kind, provider_id, target, effective_from,
                                        "exact name; implied birth date spread 0d; never same event")))


def amend(*rows):
    amendments = parse_amendments(rows)
    check_amendments(AMENDABLE_BASE, amendments, ACTIVATED_ON)
    return amendments


def test_amendments_add_aliases_and_overrides_only_from_their_effective_day():
    amendments = amend(amendment("266722", "266652"), amendment("223410", "79460", "2026-11-09", "override"))
    before = effective_registry(AMENDABLE_BASE, amendments, date(2026, 11, 7))
    assert before == AMENDABLE_BASE
    first = effective_registry(AMENDABLE_BASE, amendments, date(2026, 11, 8))
    assert first.canonical == {("WTA", "310000"): "201000", ("WTA", "266722"): "266652"}
    assert first.local_overrides == AMENDABLE_BASE.local_overrides
    both = effective_registry(AMENDABLE_BASE, amendments, date(2026, 11, 9))
    assert both.local_overrides == {("WTA", "213873"): 53141, ("WTA", "223410"): 79460}
    assert both.version == AMENDABLE_BASE.version and both.proposed == 0


def test_an_amended_alias_merges_history_like_a_base_alias():
    amendments = amend(amendment("320000", "202000"))
    registry = effective_registry(AMENDABLE_BASE, amendments, date(2026, 11, 8))
    renamed = normalize_identities(replace(BASE, event_id="2026-9", loser_id="320000"), registry)
    assert renamed.loser_id == "202000"
    with pytest.raises(TennisEloContractError, match="self-match"):
        normalize_identities(replace(BASE, winner_id="310000", loser_id="320000",
                                     event_id="2026-9"), effective_registry(
            AMENDABLE_BASE, amend(amendment("320000", "201000")), date(2026, 11, 8)))


@pytest.mark.parametrize("rows", [
    [amendment("310000", "201999")],
    [amendment("201000", "201999")],
    [amendment("213873", "201999")],
    [amendment("330000", "310000")],
    [amendment("330000", "340000"), amendment("340000", "201000")],
    [amendment("340000", "201000"), amendment("330000", "340000")],
    [amendment("330000", "201000"), amendment("330000", "202000", "2026-11-09")],
    [amendment("330000", "330000")],
    [amendment("213873", "1", kind="override")],
    [amendment("310000", "7", kind="override")],
    [amendment("330000", "53141", kind="override")],
    [amendment("330000", "201000"), amendment("330000", "7", "2026-11-09", "override")],
    [amendment("330000", "7", kind="override"), amendment("330000", "201000", "2026-11-09")],
    [amendment("330000", "201000", "2026-11-06")],
    [amendment("330000", "201000", "2026-10-30")],
], ids=["alters-base-alias", "aliases-base-canonical", "aliases-overridden-key", "targets-base-alias",
        "chain-forward", "chain-backward", "duplicate", "self-alias", "re-overrides-key",
        "overrides-an-alias", "override-target-taken", "override-after-alias", "alias-after-override",
        "activation-day", "before-activation"])
def test_amendments_that_would_alter_chain_or_predate_the_base_stop(rows):
    with pytest.raises(TennisEloContractError):
        amend(*rows)


@pytest.mark.parametrize("rows", [
    [amendment("330000", "201000", "2026-11-09"), amendment("340000", "202000", "2026-11-08")],
    [{**amendment("330000", "201000"), "status": "verified"}],
    [amendment("330000", "201000", "11/08/2026")],
    [amendment("330000", "201000", kind="merge")],
    [amendment("330000", "0", kind="override")],
    [{**amendment("330000", "201000"), "evidence": " "}],
    [amendment("330000", "201000", namespace="ITF")],
], ids=["out-of-order", "status-column", "bad-date", "bad-kind", "bad-local-id", "no-evidence", "bad-namespace"])
def test_malformed_or_reordered_amendment_rows_stop(rows):
    with pytest.raises(TennisEloContractError):
        parse_amendments(rows)


def test_a_base_with_proposed_rows_cannot_be_amended():
    base = parse_identity_registry([alias("310000", "201000"), alias("I0A0", "I0B0", "ATP", "proposed")], [])
    with pytest.raises(TennisEloContractError, match="proposed"):
        check_amendments(base, parse_amendments([amendment("330000", "201000")]), ACTIVATED_ON)


def test_stored_prefix_proves_amendments_were_only_appended():
    rows = [amendment("330000", "201000"), amendment("340000", "202000", "2026-11-09")]
    stored = parse_amendments(rows)
    count, digest = len(stored), amendments_sha256(stored)
    appended = parse_amendments([*rows, amendment("350000", "203000", "2026-11-10")])
    assert extends_prefix(appended, count, digest) and extends_prefix(stored, 0, amendments_sha256(()))
    edited = parse_amendments([rows[0], {**rows[1], "evidence": "different evidence"}])
    reordered = parse_amendments([amendment("340000", "202000"), amendment("330000", "201000")])
    for changed in (edited, reordered, stored[:1]):
        assert not extends_prefix(changed, count, digest)


def test_tracked_amendments_file_is_empty_while_the_contract_is_dormant():
    with (ingest.REGISTRY_DIR / "tennis_elo_identity_amendments.csv").open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == AMENDMENT_COLUMNS
        assert parse_amendments(reader) == ()


def resolve(amendments, day=date(2026, 11, 8), contract=IDENTITY_CONTRACT, activated_on=ACTIVATED_ON):
    return resolve_identity(AMENDABLE_BASE, parse_amendments(amendments), day,
                            contract=contract, activated_on=activated_on)


def test_unpinned_contract_keeps_the_base_and_refuses_any_amendment():
    dormant = resolve([], contract=None, activated_on=ACTIVATED_ON)
    assert dormant.registry == AMENDABLE_BASE and dormant.amendment_count is None
    assert dormant.amendments_sha256 is None
    with pytest.raises(TennisEloContractError, match="pinned identity contract"):
        resolve([amendment("330000", "201000")], contract=None)


def test_pinned_contract_applies_only_the_amendments_already_in_effect():
    rows = [amendment("330000", "201000"), amendment("340000", "202000", "2026-11-09")]
    first = resolve(rows)
    assert first.registry.canonical[("WTA", "330000")] == "201000"
    assert ("WTA", "340000") not in first.registry.canonical
    assert (first.amendment_count, first.amendments_sha256) == (1, amendments_sha256(parse_amendments(rows[:1])))
    assert resolve([]).amendment_count == 0 and resolve([], activated_on=None).amendment_count == 0


@pytest.mark.parametrize("rows, contract, activated_on, message", [
    ([], "tennis-elo-identity-contract-v0", ACTIVATED_ON, "Unknown"),
    ([amendment("330000", "201000")], IDENTITY_CONTRACT, None, "before activation"),
    ([amendment("310000", "201999")], IDENTITY_CONTRACT, ACTIVATED_ON, "alter or chain"),
])
def test_pinned_contract_stops_on_an_unknown_version_early_rows_or_a_violation(rows, contract, activated_on, message):
    with pytest.raises(TennisEloContractError, match=message):
        resolve(rows, contract=contract, activated_on=activated_on)


DORMANT_MANIFEST_KEYS = {"source", "as_of_date", "computed_at", "mapping_sha256", "ratings_sha256",
                         "identity_version", "identity_sha256", "files"}


def write_amendments(directory, rows):
    with (directory / ingest.AMENDMENTS_FILE).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AMENDMENT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def pinned_experiment(tmp_path):
    path = tmp_path / "experiment.json"
    record = json.loads(ingest.EXPERIMENT_PATH.read_text(encoding="utf-8"))
    record.update(identity_contract=IDENTITY_CONTRACT, activated_at="2026-10-18T12:00:00+00:00")
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def test_dormant_refresh_writes_todays_manifest_keys_and_stops_on_any_amendment(rows, tmp_path, monkeypatch):
    registry_dir = tmp_path / "registry"
    write_registry(registry_dir, [], [])
    writes, _, _ = setup_run(monkeypatch, tmp_path, rows[:1])
    preview = asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir))
    assert set(json.loads(preview.manifest_path.read_bytes())) == DORMANT_MANIFEST_KEYS
    write_amendments(registry_dir, [amendment("Z999", "A001", "2026-10-20", namespace="ATP")])
    with pytest.raises(TennisEloContractError, match="pinned identity contract"):
        asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir))
    assert writes == []


def test_pinned_refresh_replays_with_amendments_in_effect_and_records_them(rows, tmp_path, monkeypatch, capsys):
    registry_dir, experiment = tmp_path / "registry", pinned_experiment(tmp_path)
    write_registry(registry_dir, [], [])
    in_effect = amendment("Z999", "A001", "2026-10-20", namespace="ATP")
    write_amendments(registry_dir, [in_effect])
    setup_run(monkeypatch, tmp_path, [dict(rows[0], winner_id="Z999")])
    preview = asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir, experiment_path=experiment))
    manifest = json.loads(preview.manifest_path.read_bytes())
    assert manifest["amendment_count"] == 1
    assert manifest["amendments_sha256"] == amendments_sha256(parse_amendments([in_effect]))
    assert "provider=ATP:A001" in capsys.readouterr().out
    write_amendments(registry_dir, [in_effect, amendment("Y888", "B002", "2026-10-21", namespace="ATP")])
    reproduced = asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir, experiment_path=experiment,
                                        manifest_path=preview.manifest_path))
    assert reproduced.manifest_path == preview.manifest_path
    write_amendments(registry_dir, [{**in_effect, "evidence": "edited after review"}])
    with pytest.raises(ValueError, match="identity registry changed"):
        asyncio.run(ingest.run(cache_dir=tmp_path, registry_dir=registry_dir, experiment_path=experiment,
                               manifest_path=preview.manifest_path))
