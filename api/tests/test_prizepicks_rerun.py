"""A same-day re-run of the tennis PrizePicks ingest must keep the day's frozen
snapshots (F-20). It used to delete every row fetched today and reinsert them,
and `prop_projection_snapshots` cascades on that delete.

The fake session records each statement and answers the refresh UPDATE with a
fixed id or none, so these exercise which statements run and with what keys.
"""
import asyncio
import datetime as dt

import pytest

from app.ingest import prizepicks
from app.repositories import props as props_repo
from app.repositories.props import PulledProps, get_today_props, retire_pulled_today_props, store_today_prop

START = dt.datetime(2026, 11, 6, 15, 0, tzinfo=dt.timezone.utc)


class _Result:
    def __init__(self, value=None, rowcount=0):
        self._value = value
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        assert self._value is not None
        return self._value

    def fetchall(self):
        return []


class _Session:
    def __init__(self, refreshed_id=None, inserted_id=900, deleted=0, withdrawn=0):
        self.refreshed_id = refreshed_id
        self.inserted_id = inserted_id
        self.deleted = deleted
        self.withdrawn = withdrawn
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, params))
        if sql.lstrip().startswith("UPDATE"):
            return _Result(self.refreshed_id, rowcount=self.withdrawn)
        if sql.lstrip().startswith("INSERT"):
            return _Result(self.inserted_id)
        return _Result(rowcount=self.deleted)


def _store(db, player_id=7, raw_json=None):
    return asyncio.run(store_today_prop(
        db, player_id=player_id, match_id=None, source="prizepicks", stat_type="Total Games",
        line=21.5, odds_type=None, start_time=START, raw_json=raw_json or {"player_name": "A. Player"},
    ))


def test_a_line_already_stored_today_is_refreshed_and_keeps_its_id():
    db = _Session(refreshed_id=41)

    assert _store(db) == 41
    assert [sql.lstrip().split()[0] for sql, _ in db.calls] == ["UPDATE"]


def test_a_new_line_is_inserted():
    db = _Session(refreshed_id=None, inserted_id=900)

    assert _store(db) == 900
    assert [sql.lstrip().split()[0] for sql, _ in db.calls] == ["UPDATE", "INSERT"]


def test_an_unresolved_player_is_matched_by_the_feed_name():
    db = _Session()

    _store(db, player_id=None, raw_json={"player_name": "Unknown Qualifier"})

    sql, params = db.calls[0]
    assert params["pid"] is None
    assert params["player_name"] == "Unknown Qualifier"
    assert "COALESCE(p.player_id::text, NULLIF(p.raw_json ->> 'player_name', ''))" in sql


def test_the_refresh_only_matches_lines_fetched_today():
    db = _Session()

    _store(db)

    assert "p.fetched_at >= CURRENT_DATE" in db.calls[0][0]


def _retire(db):
    return asyncio.run(retire_pulled_today_props(db, "prizepicks", [41, 900]))


def test_pulled_lines_with_a_snapshot_are_withdrawn_and_the_rest_deleted():
    db = _Session(deleted=3, withdrawn=2)

    assert _retire(db) == PulledProps(deleted=3, withdrawn=2)
    (withdraw_sql, withdraw_params), (delete_sql, delete_params) = db.calls
    assert withdraw_sql.lstrip().startswith("UPDATE")
    assert "'{withdrawn}', 'true'::jsonb" in withdraw_sql
    assert "AND EXISTS (SELECT 1 FROM prop_projection_snapshots s WHERE s.prop_id = p.id)" in withdraw_sql
    assert delete_sql.lstrip().startswith("DELETE")
    assert "AND NOT EXISTS (SELECT 1 FROM prop_projection_snapshots s WHERE s.prop_id = p.id)" in delete_sql
    assert withdraw_params == delete_params == {"src": "prizepicks", "kept": [41, 900]}


def test_only_rows_not_stored_this_run_are_retired():
    db = _Session()

    _retire(db)

    for sql, _ in db.calls:
        assert "NOT (p.id = ANY(CAST(:kept AS bigint[])))" in sql
        assert "p.fetched_at >= CURRENT_DATE" in sql


def test_the_board_skips_withdrawn_rows():
    db = _Session()

    asyncio.run(get_today_props(db, source="prizepicks"))

    assert "AND NOT COALESCE((p.raw_json ->> 'withdrawn')::boolean, false)" in db.calls[0][0]


def test_a_refresh_replaces_raw_json_so_a_reoffered_line_is_live_again():
    db = _Session(refreshed_id=41)

    _store(db, raw_json={"player_name": "A. Player"})

    sql, params = db.calls[0]
    assert "raw_json = CAST(:raw AS jsonb)" in sql
    assert "withdrawn" not in params["raw"]


@pytest.fixture
def stored(monkeypatch):
    """`_store_props` with player and match lookups stubbed and each stored id recorded."""
    ids = iter([41, 900])
    pruned: list[list[int]] = []

    async def no_player(*_args):
        return None

    async def store(_db, **_kwargs):
        return next(ids)

    async def prune(_db, source, kept_ids):
        assert source == "prizepicks"
        pruned.append(list(kept_ids))
        return PulledProps(deleted=0, withdrawn=0)

    monkeypatch.setattr("app.repositories.players.resolve_player", no_player)
    monkeypatch.setattr(props_repo, "store_today_prop", store)
    monkeypatch.setattr(props_repo, "retire_pulled_today_props", prune)
    return pruned


FEED = [
    {"player_name": "A. Player", "tour": None, "stat_type": "Aces", "line": 4.5, "odds_type": None,
     "start_time": None, "raw_json": {}},
    {"player_name": "B. Player", "tour": None, "stat_type": "Aces", "line": 5.5, "odds_type": None,
     "start_time": None, "raw_json": {}},
]


def test_a_full_run_prunes_with_the_ids_it_stored(stored):
    count = asyncio.run(prizepicks._store_props(object(), FEED, prune_pulled=True))

    assert count == 2
    assert stored == [[41, 900]]


def test_a_run_with_a_failed_league_deletes_nothing(stored):
    asyncio.run(prizepicks._store_props(object(), FEED, prune_pulled=False))

    assert stored == []


def test_the_ingest_holds_no_sql():
    source = open(prizepicks.__file__, encoding="utf-8").read()

    assert "DELETE FROM" not in source
    assert "sqlalchemy" not in source
