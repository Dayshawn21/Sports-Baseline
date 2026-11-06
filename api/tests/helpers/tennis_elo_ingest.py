"""Shared fixtures and builders, first written for `test_tennis_elo_ingest.py`."""
import csv
import hashlib
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pytest

from app.core.tennis_elo import TennisEloMatch, parse_row
from app.core.tennismylife import PlayerNameIndex
from app.ingest import tennis_elo as ingest


NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)
SOURCE = ingest.SourceFile("ATP", "2026.csv")
INDEX = PlayerNameIndex(canonical={("player one", "ATP"): 11, ("player two", "ATP"): 22}, aliases={})


@pytest.fixture
def rows():
    with (Path(__file__).parents[1] / "fixtures/tennis_elo_results.csv").open(encoding="utf-8") as handle:
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
