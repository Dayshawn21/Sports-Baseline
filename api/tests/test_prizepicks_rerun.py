"""A same-day re-run of the tennis PrizePicks ingest must keep the day's frozen
snapshots (F-20). It used to delete every row fetched today and reinsert them,
and `prop_projection_snapshots` cascades on that delete.

The fake session records each statement and answers the refresh UPDATE with a
fixed id or none, so these exercise which statements run and with what keys.
"""
import asyncio
import datetime as dt
import re

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


def _squash(sql: str) -> str:
    return re.sub(r"\s+\)", ")", re.sub(r"\(\s+", "(", " ".join(sql.split())))


def _distinct_on_terms(sql: str) -> list[str]:
    """The comma-separated terms of the first DISTINCT ON (...), whitespace collapsed."""
    body = sql[sql.index("DISTINCT ON (") + len("DISTINCT ON ("):]
    terms, current, depth = [], "", 0
    for ch in body:
        if ch == ")" and depth == 0:
            break
        if ch == "," and depth == 0:
            terms.append(current)
            current = ""
            continue
        depth += {"(": 1, ")": -1}.get(ch, 0)
        current += ch
    terms.append(current)
    return [_squash(term) for term in terms]


def test_the_refresh_key_is_the_board_key():
    """A refresh matching on fewer or other columns than the board collapses on
    would update a row the board no longer shows, or insert a second copy."""
    db = _Session()
    asyncio.run(get_today_props(db, source="prizepicks"))
    board = _distinct_on_terms(db.calls[0][0])
    refresh = _squash(props_repo._SAME_TODAY_LINE)
    identity = "COALESCE(p.player_id::text, NULLIF(p.raw_json ->> 'player_name', '')"

    assert board[0] == "p.source" and "p.source = :src" in refresh
    assert board[1].startswith(identity) and identity in refresh
    for column in board[2:]:
        assert f"{column} = " in refresh or f"{column} IS NOT DISTINCT FROM " in refresh, column
    assert len(board) == 6


def test_the_refresh_compares_the_line_at_the_column_precision():
    db = _Session()

    _store(db)

    assert "p.line = CAST(:line AS numeric(6,1))" in db.calls[0][0]


@pytest.fixture
def leagues(monkeypatch):
    """Two tennis leagues where league 2 fails, with each fetch recorded."""
    fetched: list[int] = []

    async def projections(_client, league_id):
        fetched.append(league_id)
        if league_id == 2:
            raise RuntimeError("feed down")
        return {"league": league_id}

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(prizepicks, "_fetch_projections", projections)
    monkeypatch.setattr(prizepicks, "_parse_projections", lambda _raw, _league_id: list(FEED))
    monkeypatch.setattr(prizepicks.asyncio, "sleep", no_sleep)
    return fetched


def test_a_failed_league_is_counted_and_the_others_kept(leagues):
    props, failed = asyncio.run(prizepicks._fetch_league_props(object(), [1, 2, 3]))

    assert leagues == [1, 2, 3]
    assert failed == 1
    assert len(props) == 2 * len(FEED)


class _SessionScope:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def commit(self):
        return None


@pytest.mark.parametrize(("league_ids", "prunes"), [([1, 3], True), ([1, 2], False)])
def test_run_prunes_only_when_every_league_fetched(leagues, monkeypatch, league_ids, prunes):
    seen: list[bool] = []

    async def tennis_leagues(_client):
        return [{"id": lg, "attributes": {"name": f"Tennis {lg}"}} for lg in league_ids]

    async def store(_db, props, *, prune_pulled):
        seen.append(prune_pulled)
        return len(props)

    monkeypatch.setattr(prizepicks, "_fetch_leagues", tennis_leagues)
    monkeypatch.setattr(prizepicks, "_store_props", store)
    monkeypatch.setattr("app.db.pool.SessionLocal", _SessionScope)

    asyncio.run(prizepicks.run())

    assert seen == [prunes]
