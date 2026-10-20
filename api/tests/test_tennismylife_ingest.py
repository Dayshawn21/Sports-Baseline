import asyncio
import csv
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
import httpx

from app.ingest import tennismylife
from app.core.tennismylife import PlayerNameIndex
from app.ingest.tennismylife import Counts, SourceFile, collect_rows, source_files

TODAY = date(2026, 10, 20)
SOURCE = SourceFile("ATP", "ATP", "2026.csv")
INDEX = PlayerNameIndex(canonical={
    ("sebastian baez", "ATP"): 11, ("jaume munar", "ATP"): 22,
}, aliases={})


@pytest.fixture
def rows() -> list[dict[str, str]]:
    path = Path(__file__).parent / "fixtures" / "tennismylife.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _csv(rows: list[dict[str, str]]) -> str:
    contents = StringIO()
    writer = csv.DictWriter(contents, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return contents.getvalue()


def test_files_cover_all_families_with_yearly_files_before_the_three_ongoing_files():
    files = source_files(date(2026, 9, 29), TODAY)
    assert [file.path for file in files] == [
        "2026.csv", "2026_challenger.csv", "atp_quali/2026_atp_quali.csv", "2026_wta.csv",
        "ongoing_tourneys.csv", "challenger_ongoing_tourneys.csv", "wta_ongoing_tourneys.csv",
    ]
    assert [file.tour for file in files] == ["ATP", "ATP", "ATP", "WTA", "ATP", "ATP", "WTA"]


def test_since_adds_earlier_years_and_keeps_ongoing_files_once():
    files = source_files(date(2024, 12, 20), TODAY)
    assert len(files) == 15
    assert files[0].path == "2024.csv" and files[4].path == "2025.csv" and files[8].path == "2026.csv"
    assert sum(file.path == "ongoing_tourneys.csv" for file in files) == 1


def test_cutoff_is_inclusive_and_counts_old_rows_as_read(rows):
    counts, pending = Counts(), {}
    collect_rows(_csv(rows[:1]), SOURCE, date(2026, 1, 2), INDEX, pending, counts)
    assert (counts.rows_read, counts.rows_kept, counts.unique) == (1, 1, 2)
    assert {stat.player_id for _, stat in pending.values()} == {11, 22}
    old_counts, old_pending = Counts(), {}
    collect_rows(_csv(rows[:1]), SOURCE, date(2026, 1, 3), INDEX, old_pending, old_counts)
    assert (old_counts.rows_read, old_counts.rows_kept) == (1, 0)
    assert old_pending == {}


def test_yearly_copy_wins_and_other_players_with_the_same_key_are_kept(rows):
    counts, pending = Counts(), {}
    collect_rows(_csv(rows[:1]), SOURCE, date(2026, 1, 1), INDEX, pending, counts)
    ongoing = dict(rows[0], w_ace="99", l_ace="99")
    collect_rows(_csv([ongoing]), SourceFile("ATP", "ATP", "ongoing_tourneys.csv"),
                 date(2026, 1, 1), INDEX, pending, counts)
    assert (len(pending), counts.unique, counts.duplicates) == (2, 2, 2)
    assert sorted(stat.aces for _, stat in pending.values()) == [0, 7]


def test_bad_rows_no_stats_and_unknown_players_are_skipped_and_counted(rows, caplog):
    bad = dict(rows[0], tourney_date="20260230")
    counts, pending = Counts(), {}
    collect_rows(_csv([bad, rows[3], rows[4], rows[1], rows[0]]), SOURCE,
                 date(2026, 1, 1), INDEX, pending, counts)
    assert (counts.rows_read, counts.rows_kept, counts.bad_rows) == (5, 4, 1)
    assert (counts.no_stats, counts.unknown, counts.unique, counts.stored) == (4, 2, 2, 0)
    assert "Skipping 2026.csv row 2" in caplog.text
    assert len(pending) == 2


def test_unknown_side_does_not_prevent_storing_a_known_opponent(rows):
    counts, pending = Counts(), {}
    index = PlayerNameIndex(canonical={("sebastian baez", "ATP"): 11}, aliases={})
    collect_rows(_csv(rows[:1]), SOURCE, date(2026, 1, 1), index, pending, counts)
    assert (counts.unknown, counts.unique) == (1, 1)
    (family, stat), = pending.values()
    assert (family, stat.player_id, stat.opponent_name, stat.aces, stat.double_faults) == (
        "ATP", 11, "Jaume Munar", 0, 2,
    )


def _patch_run(rows, monkeypatch, fail_download=False):
    writes, sessions = [], []

    class Session:
        commits = 0

        async def __aenter__(self):
            sessions.append(self)
            return self

        async def __aexit__(self, *_args):
            pass

        async def commit(self):
            self.commits += 1

    async def index(_db):
        return INDEX

    async def download(_client, _path):
        if fail_download and _path == "wta_ongoing_tourneys.csv":
            raise httpx.ConnectError("download failed")
        return _csv(rows[:1])

    async def write(_db, stats, *, source):
        writes.append((stats, source))

    monkeypatch.setattr(tennismylife, "SessionLocal", Session)
    monkeypatch.setattr(tennismylife, "get_player_name_index", index)
    monkeypatch.setattr(tennismylife, "_download", download)
    monkeypatch.setattr(tennismylife, "upsert_player_match_stats", write)
    monkeypatch.setattr(tennismylife, "BATCH_SIZE", 1)
    return writes, sessions


@pytest.mark.parametrize("dry_run", [True, False])
def test_run_dry_run_never_writes_and_real_run_batches_deduplicated_rows(rows, monkeypatch, dry_run):
    writes, sessions = _patch_run(rows, monkeypatch)
    counts = asyncio.run(tennismylife.run(date(2026, 1, 1), dry_run=dry_run))
    if dry_run:
        assert len(sessions) == 1 and sessions[0].commits == 0
        assert writes == [] and sum(c.stored for c in counts.values()) == 0
    else:
        assert len(sessions) == 2 and sessions[1].commits == 1
        assert len(writes) == 2 and all(len(stats) == 1 and source == "tennismylife" for stats, source in writes)
        assert sum(c.stored for c in counts.values()) == 2


def test_a_failed_last_download_aborts_before_any_write(rows, monkeypatch):
    writes, sessions = _patch_run(rows, monkeypatch, fail_download=True)
    with pytest.raises(httpx.ConnectError, match="download failed"):
        asyncio.run(tennismylife.run(date(2026, 1, 1)))
    assert writes == [] and len(sessions) == 1 and sessions[0].commits == 0
