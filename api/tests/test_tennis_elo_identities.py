import asyncio
import csv
import random
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.core.tennis_elo import (
    IDENTITY_COLUMNS, OVERRIDE_COLUMNS, IdentityRegistry, TennisEloContractError, TennisEloMatch,
    TennisEloReplay, deduplicate, normalize_identities, parse_identity_registry,
)
from app.core.tennismylife import PlayerNameIndex
from app.ingest import tennis_elo as ingest
from tests.test_tennis_elo_ingest import INDEX, cached, matches, rows, setup_run  # noqa: F401

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
    assert "Identity registry tennis-elo-identities-v2" in capsys.readouterr().out
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
