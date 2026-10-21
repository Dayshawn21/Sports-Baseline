import asyncio
import csv
import hashlib
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import httpx
import pytest

from app.core.tennis_elo import TennisEloContractError, TennisEloMatch, parse_row
from app.core.tennismylife import PlayerNameIndex
from app.ingest import tennis_elo as ingest

NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
DAY = NOW.date()
SOURCE = ingest.SourceFile("ATP", "2026.csv")
INDEX = PlayerNameIndex(canonical={("player one", "ATP"): 11, ("player two", "ATP"): 22}, aliases={})


@pytest.fixture
def rows():
    with (Path(__file__).parent / "fixtures/tennis_elo_results.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def contents(rows):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def cached(tmp_path, rows, source=SOURCE):
    data = contents(rows)
    sha = hashlib.sha256(data).hexdigest()
    ingest._immutable_write(tmp_path / "files" / f"{sha}.csv", data)
    return ingest.DownloadedFile(source, sha, NOW - timedelta(minutes=1))


def matches(rows):
    result = parse_row(rows[0], "ATP")
    assert isinstance(result, TennisEloMatch)
    return result


def test_file_inventory_is_fixed_from_2021_with_ongoing_files_last():
    sources = ingest.source_files(DAY)
    assert len(sources) == 27
    assert sources[:4] == [ingest.SourceFile("ATP", "2021.csv"),
                          ingest.SourceFile("CHALLENGER", "2021_challenger.csv"),
                          ingest.SourceFile("ATP_QUALI", "atp_quali/2021_atp_quali.csv"),
                          ingest.SourceFile("WTA", "2021_wta.csv")]
    assert [s.path for s in sources[-3:]] == ["ongoing_tourneys.csv", "challenger_ongoing_tourneys.csv", "wta_ongoing_tourneys.csv"]


def test_verified_generic_tour_labels_remain_inside_the_original_families(rows):
    assert isinstance(parse_row(dict(rows[0], tourney_level="A", round="Q1"), "ATP_QUALI"), TennisEloMatch)
    for event in ("2025-1082", "2025-2084"):
        assert isinstance(parse_row(dict(rows[0], tourney_level="A", tourney_id=event), "WTA"), TennisEloMatch)
    with pytest.raises(TennisEloContractError, match="Unverified TennisMyLife WTA A-level"):
        parse_row(dict(rows[0], tourney_level="A"), "WTA")


def test_collect_counts_bad_and_excluded_rows_and_enforces_both_date_cutoffs(rows, tmp_path):
    file = cached(tmp_path, [*rows, dict(rows[0], tourney_date="20201001"),
                             dict(rows[0], tourney_date="20261020"), dict(rows[0], tourney_date="bad")])
    results, counts = ingest.collect_matches([file], tmp_path, DAY)
    count = counts["ATP"]
    assert len(results) == 2
    assert (count.rows, count.admitted, count.malformed) == (8, 2, 1)
    assert count.excluded == {"retirement": 1, "walkover": 1, "unfinished": 1, "outside cutoff": 2}


def test_annual_and_identical_ongoing_results_count_once(rows, tmp_path):
    annual = cached(tmp_path, rows[:1])
    ongoing = replace(annual, source=ingest.SourceFile("ATP", "ongoing_tourneys.csv"))
    results, counts = ingest.collect_matches([annual, ongoing], tmp_path, DAY)
    assert len(results) == 1 and counts["ATP"].duplicates == 1
    conflict = cached(tmp_path, [dict(rows[0], score="6-0 6-0")], ongoing.source)
    with pytest.raises(TennisEloContractError, match="Conflicting ELO match copies"):
        ingest.collect_matches([annual, conflict], tmp_path, DAY)


def test_stray_main_draw_copy_in_qualifying_file_is_removed_only_on_exact_agreement(rows, tmp_path):
    main = cached(tmp_path, rows[:1])
    qualifying = replace(main, source=ingest.SourceFile("ATP_QUALI", "atp_quali/2026_atp_quali.csv"))
    results, counts = ingest.collect_matches([main, qualifying], tmp_path, DAY)
    assert len(results) == 1 and counts["ATP_QUALI"].duplicates == 1
    with pytest.raises(TennisEloContractError, match="Unverified main-draw row"):
        ingest.collect_matches([qualifying], tmp_path, DAY)
    revised = cached(tmp_path, [dict(rows[0], score="6-0 6-0")], qualifying.source)
    with pytest.raises(TennisEloContractError, match="Unverified main-draw row"):
        ingest.collect_matches([main, revised], tmp_path, DAY)


@pytest.mark.parametrize("change", [{"round": "NEW"}, {"tourney_level": "NEW"}])
def test_unverified_contract_is_fatal_instead_of_silently_dropping_history(rows, tmp_path, change):
    file = cached(tmp_path, [dict(rows[0], **change)])
    with pytest.raises(TennisEloContractError):
        ingest.collect_matches([file], tmp_path, DAY)


def test_missing_columns_empty_annual_and_corrupt_cache_fail(rows, tmp_path):
    file = cached(tmp_path, rows[:1])
    path = tmp_path / "files" / f"{file.sha256}.csv"
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="hash mismatch"):
        ingest.collect_matches([file], tmp_path, DAY)
    for data, error in [(b"winner_id\nA\n", "columns changed"),
                        (contents(rows[:1]).split(b"\r\n")[0] + b"\r\n", "Empty required annual")]:
        sha = hashlib.sha256(data).hexdigest()
        ingest._immutable_write(tmp_path / "files" / f"{sha}.csv", data)
        with pytest.raises(TennisEloContractError, match=error):
            ingest.collect_matches([replace(file, sha256=sha)], tmp_path, DAY)


def test_cache_is_immutable(tmp_path):
    path = tmp_path / "blob"
    ingest._immutable_write(path, b"first")
    ingest._immutable_write(path, b"first")
    with pytest.raises(ValueError, match="Immutable ELO cache conflict"):
        ingest._immutable_write(path, b"replacement")
    assert path.read_bytes() == b"first"


def test_alias_variants_map_only_to_the_matching_namespace(rows):
    first = matches(rows)
    variant = replace(first, winner_name="P One", match_number=20)
    index = PlayerNameIndex(INDEX.canonical, {"p one": 11})
    result = ingest.map_players([first, variant], index)
    assert result.linked == {("ATP", "A001"): 11, ("ATP", "B002"): 22}
    assert result.conflicts == []
    wrong_tour = replace(first, namespace="WTA", family="WTA", winner_name="P One")
    assert ingest.map_players([wrong_tour], index).linked == {}


def test_one_provider_id_resolving_to_multiple_local_players_is_a_conflict(rows):
    first = matches(rows)
    other = replace(first, winner_name="Different Name", match_number=20)
    index = PlayerNameIndex({**INDEX.canonical, ("different name", "ATP"): 33}, {})
    result = ingest.map_players([first, other], index)
    assert ("ATP", "A001") not in result.linked
    assert result.ambiguous == 1 and len(result.conflicts) == 1


def test_multiple_provider_ids_cannot_share_a_local_player(rows):
    first = matches(rows)
    result = ingest.map_players([first, replace(first, winner_id="OTHER", match_number=20)], INDEX)
    assert result.linked == {("ATP", "B002"): 22}
    assert result.ambiguous == 2 and len(result.conflicts) == 1


def setup_run(monkeypatch, tmp_path, rows, index=INDEX):
    file = cached(tmp_path, rows)
    writes, sessions, stored = [], [], []

    class Session:
        commits = 0

        async def __aenter__(self):
            sessions.append(self)
            return self

        async def __aexit__(self, *_args):
            pass

        async def commit(self):
            self.commits += 1

    async def get_existing(_db, **_kwargs):
        return list(stored)

    async def get_index(_db):
        return index

    async def download(_day, _cache):
        return [file]

    async def write(_db, snapshots):
        writes.append(snapshots)
        stored.extend(snapshots)
        return len(snapshots)

    monkeypatch.setattr(ingest, "_now", lambda: NOW)
    monkeypatch.setattr(ingest, "source_files", lambda _day: [SOURCE])
    monkeypatch.setattr(ingest, "SessionLocal", Session)
    monkeypatch.setattr(ingest, "get_daily_snapshots", get_existing)
    monkeypatch.setattr(ingest, "get_player_name_index", get_index)
    monkeypatch.setattr(ingest, "download_files", download)
    monkeypatch.setattr(ingest, "insert_daily_snapshots", write)
    return writes, sessions, stored


def test_default_dry_run_keeps_untracked_opponents_in_replay_but_never_writes(rows, tmp_path, monkeypatch, capsys):
    index = PlayerNameIndex({("player one", "ATP"): 11}, {})
    writes, sessions, _ = setup_run(monkeypatch, tmp_path, rows[:1], index)
    result = asyncio.run(ingest.run(cache_dir=tmp_path))
    assert result.candidates == 1 and result.inserted == 0 and not result.blocked
    assert writes == [] and all(s.commits == 0 for s in sessions)
    manifest = json.loads(result.manifest_path.read_bytes())
    assert result.manifest_path.stem == hashlib.sha256(result.manifest_path.read_bytes()).hexdigest()
    assert manifest["source"] == ingest.SOURCE
    assert "Replay: 1 matches, 2 players" in capsys.readouterr().out


def test_reviewed_manifest_writes_exact_plan_then_retry_reuses_without_downloading(rows, tmp_path, monkeypatch):
    writes, sessions, stored = setup_run(monkeypatch, tmp_path, rows[:1])
    preview = asyncio.run(ingest.run(cache_dir=tmp_path))
    result = asyncio.run(ingest.run(cache_dir=tmp_path, dry_run=False, manifest_path=preview.manifest_path))
    assert result.inserted == 2 and len(writes) == 1 and sessions[-1].commits == 1
    assert all(s.manifest_sha256 == preview.manifest_path.stem and s.computed_at == NOW for s in stored)
    assert stored[0].rating.overall > 1500

    async def no_download(*_args):
        raise AssertionError("Retry downloaded data")

    monkeypatch.setattr(ingest, "download_files", no_download)
    retry = asyncio.run(ingest.run(cache_dir=tmp_path, dry_run=False))
    assert retry.reused and retry.inserted == 0 and len(writes) == 1
    with pytest.raises(ValueError, match="different ELO daily manifest"):
        asyncio.run(ingest.run(cache_dir=tmp_path, manifest_path=Path("different.json")))


def test_any_identity_conflict_blocks_the_entire_write(rows, tmp_path, monkeypatch):
    conflict = dict(rows[0], winner_id="OTHER", match_num="20")
    writes, sessions, _ = setup_run(monkeypatch, tmp_path, [rows[0], conflict])
    result = asyncio.run(ingest.run(cache_dir=tmp_path, dry_run=False))
    assert result.blocked and writes == [] and all(s.commits == 0 for s in sessions)


def test_failed_required_download_or_contract_error_cannot_write_a_partial_snapshot(rows, tmp_path, monkeypatch):
    writes, sessions, _ = setup_run(monkeypatch, tmp_path, rows[:1])

    async def failed(*_args):
        raise httpx.ConnectError("required download failed")

    monkeypatch.setattr(ingest, "download_files", failed)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(ingest.run(cache_dir=tmp_path, dry_run=False))
    assert writes == [] and all(s.commits == 0 for s in sessions)


def test_changed_name_mapping_cannot_reinterpret_a_reviewed_manifest(rows, tmp_path, monkeypatch):
    writes, _, _ = setup_run(monkeypatch, tmp_path, rows[:1])
    preview = asyncio.run(ingest.run(cache_dir=tmp_path))

    async def changed(_db):
        return PlayerNameIndex({("player one", "ATP"): 99, ("player two", "ATP"): 22}, {})

    monkeypatch.setattr(ingest, "get_player_name_index", changed)
    with pytest.raises(ValueError, match="no longer reproduces"):
        asyncio.run(ingest.run(cache_dir=tmp_path, dry_run=False, manifest_path=preview.manifest_path))
    assert writes == []


@pytest.mark.parametrize("field,value", [("source", "other"), ("as_of_date", "2026-10-19"),
                                        ("computed_at", "2026-10-20T12:00:00+00:00")])
def test_manifest_provenance_changes_fail_before_write(rows, tmp_path, monkeypatch, field, value):
    writes, _, _ = setup_run(monkeypatch, tmp_path, rows[:1])
    preview = asyncio.run(ingest.run(cache_dir=tmp_path))
    record = json.loads(preview.manifest_path.read_bytes())
    record[field] = value
    raw = ingest._canonical_json(record)
    path = tmp_path / f"{hashlib.sha256(raw).hexdigest()}.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        asyncio.run(ingest.run(cache_dir=tmp_path, dry_run=False, manifest_path=path))
    assert writes == []


def test_provider_inventory_missing_or_moved_file_stops_before_file_download(tmp_path, monkeypatch):
    calls = []

    async def fetch(_client, url):
        calls.append(url)
        return b'{"files":[]}'

    monkeypatch.setattr(ingest, "_fetch", fetch)
    with pytest.raises(TennisEloContractError, match="missing or moved"):
        asyncio.run(ingest.download_files(DAY, tmp_path))
    assert calls == [ingest.MANIFEST_URL]


def test_cli_defaults_to_dry_run_and_requires_explicit_write(monkeypatch):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return ingest.RunResult(None, 0)

    monkeypatch.setattr(ingest, "run", run)
    monkeypatch.setattr("sys.argv", ["tennis_elo"])
    ingest.main()
    assert calls == [{"dry_run": True, "manifest_path": None}]
