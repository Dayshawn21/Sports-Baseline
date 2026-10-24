from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nhl_context import NhlGoalieFeed, NhlInjuryFeed, parse_goalie_feed, parse_injury_feed
from app.core.nhl_context_resolution import EventLink, PlayerLink
from app.repositories import nhl_context as repo

FETCHED = datetime(2026, 10, 24, 16, 30, tzinfo=timezone.utc)
FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class Result:
    scalar: int | None = None
    rows: list[dict[str, object]] = field(default_factory=list)
    values: list[int] = field(default_factory=list)

    def scalar_one_or_none(self) -> int | None:
        return self.scalar

    def mappings(self) -> Result:
        return self

    def one(self) -> dict[str, object]:
        assert len(self.rows) == 1
        return self.rows[0]

    def all(self) -> list[dict[str, object]]:
        return self.rows

    def scalars(self) -> ScalarResult:
        return ScalarResult(self.values)


@dataclass
class ScalarResult:
    values: list[int]

    def all(self) -> list[int]:
        return self.values


@dataclass
class Session:
    results: list[Result] = field(default_factory=list)
    fail_on: int | None = None
    calls: list[tuple[str, object]] = field(default_factory=list)
    savepoints: int = 0
    releases: int = 0
    rollbacks: int = 0

    def begin_nested(self) -> Savepoint:
        return Savepoint(self)

    async def execute(self, statement: TextClause, params: object = None) -> Result:
        self.calls.append((str(statement), params))
        if len(self.calls) == self.fail_on:
            raise SQLAlchemyError("injected entry write failure")
        assert self.results, "unexpected SQL"
        return self.results.pop(0)


@dataclass
class Savepoint:
    session: Session

    async def __aenter__(self) -> None:
        self.session.savepoints += 1

    async def __aexit__(self, kind: type[BaseException] | None, exc: BaseException | None,
                        traceback: TracebackType | None) -> None:
        if kind is None:
            self.session.releases += 1
        else:
            self.session.rollbacks += 1


def injury_feed() -> NhlInjuryFeed:
    return parse_injury_feed(json.loads((FIXTURES / "espn_nhl_injuries.json").read_text()))


def goalie_feed() -> NhlGoalieFeed:
    return parse_goalie_feed(json.loads((FIXTURES / "espn_nhl_goalies.json").read_text()), date(2026, 10, 24))


def injury_links(feed: NhlInjuryFeed) -> dict[repo.Identity, PlayerLink]:
    return {(row.espn_team_id, row.espn_athlete_id): PlayerLink(None, "no_candidate") for row in feed.injuries}


def goalie_links(feed: NhlGoalieFeed) -> dict[repo.Identity, PlayerLink]:
    return {(row.espn_event_id, row.espn_team_id): PlayerLink(None, "no_candidate") for row in feed.observations}


def game_links(feed: NhlGoalieFeed) -> dict[str, EventLink]:
    return {row.espn_event_id: EventLink(None, "no_game") for row in feed.observations}


def store_injuries(session: Session, feed: NhlInjuryFeed | None = None,
                   links: dict[repo.Identity, PlayerLink] | None = None, fetched: datetime = FETCHED) -> int:
    selected = feed if feed is not None else injury_feed()
    return asyncio.run(repo.store_injury_snapshot(
        cast(AsyncSession, session), selected, fetched, injury_links(selected) if links is None else links,
    ))


def store_goalies(session: Session, feed: NhlGoalieFeed | None = None,
                  links: dict[repo.Identity, PlayerLink] | None = None,
                  games: dict[str, EventLink] | None = None) -> int:
    selected = feed if feed is not None else goalie_feed()
    return asyncio.run(repo.store_goalie_snapshot(
        cast(AsyncSession, session), selected, FETCHED,
        goalie_links(selected) if links is None else links, game_links(selected) if games is None else games,
    ))


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
def test_unresolved_entries_are_preserved_atomically_without_outer_commit(kind: str) -> None:
    session = Session([Result(scalar=9), Result()])
    snapshot = store_injuries(session) if kind == "injuries" else store_goalies(session)
    assert snapshot == 9
    assert (session.savepoints, session.releases, session.rollbacks) == (1, 1, 0)
    assert "ON CONFLICT ON CONSTRAINT uq_nhl_context_batch DO NOTHING" in session.calls[0][0]
    header = cast(dict[str, object], session.calls[0][1])
    rows = cast(list[dict[str, object]], session.calls[1][1])
    assert len(rows) == header["entry_count"] == (3 if kind == "injuries" else 4)
    assert all(row["snapshot_id"] == 9 and row["player_id"] is None for row in rows)
    assert header["scope_date"] == (None if kind == "injuries" else date(2026, 10, 24))
    assert all(sql.strip().startswith("INSERT") for sql, _ in session.calls)


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
def test_valid_empty_feed_stores_header_only(kind: str) -> None:
    session = Session([Result(scalar=10)])
    if kind == "injuries":
        store_injuries(session, replace(injury_feed(), injuries=()))
    else:
        store_goalies(session, replace(goalie_feed(), observations=()))
    assert len(session.calls) == 1
    assert cast(dict[str, object], session.calls[0][1])["entry_count"] == 0
    assert session.releases == 1


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
def test_entry_failure_exits_savepoint_via_rollback_without_committing(kind: str) -> None:
    session = Session([Result(scalar=9)], fail_on=2)
    with pytest.raises(SQLAlchemyError, match="injected"):
        store_injuries(session) if kind == "injuries" else store_goalies(session)
    assert (session.savepoints, session.releases, session.rollbacks) == (1, 0, 1)


def retry_session(kind: str, *, empty: bool = False) -> Session:
    feed = injury_feed() if kind == "injuries" else goalie_feed()
    rows: list[dict[str, object]] = []
    if kind == "injuries":
        for row in injury_feed().injuries:
            rows.append({**asdict(row), "player_id": None, "link_reason": "no_candidate"})
    else:
        for observation in goalie_feed().observations:
            rows.append({**asdict(observation), "player_id": None, "player_link_reason": "no_candidate",
                         "game_id": None, "game_link_reason": "no_game"})
    if empty:
        rows = []
    return Session([Result(), Result(rows=[{"id": 7, "source_timestamp": feed.source_timestamp,
                                           "entry_count": len(rows)}]), Result(rows=list(reversed(rows)))])


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
@pytest.mark.parametrize("empty", [False, True])
def test_identical_retry_reuses_snapshot_independent_of_row_order(kind: str, empty: bool) -> None:
    session = retry_session(kind, empty=empty)
    if kind == "injuries":
        feed = replace(injury_feed(), injuries=()) if empty else injury_feed()
        snapshot = store_injuries(session, feed)
    else:
        feed = replace(goalie_feed(), observations=()) if empty else goalie_feed()
        snapshot = store_goalies(session, feed)
    assert snapshot == 7
    assert len(session.calls) == 3
    assert all(sql.strip().startswith("SELECT") for sql, _ in session.calls[1:])
    assert "scope_date IS NOT DISTINCT FROM :scope_date" in session.calls[1][0]


@pytest.mark.parametrize("kind", ["injuries", "goalies"])
@pytest.mark.parametrize("change", ["count", "source_time", "status", "missing_row", "player_id", "reason"])
def test_conflicting_retry_cannot_overwrite_any_content_or_frozen_link(kind: str, change: str) -> None:
    session = retry_session(kind)
    header, rows = session.results[1].rows[0], session.results[2].rows
    if change == "count":
        header["entry_count"] = 99
    elif change == "source_time":
        header["source_timestamp"] = FETCHED
    elif change == "missing_row":
        rows.pop()
    else:
        key = "link_reason" if kind == "injuries" else "player_link_reason"
        rows[0][key if change == "reason" else change] = 123 if change == "player_id" else "changed"
    with pytest.raises(ValueError, match="different contents or frozen links"):
        store_injuries(session) if kind == "injuries" else store_goalies(session)
    assert session.rollbacks == 1 and session.releases == 0


def test_goalie_game_link_and_source_timing_are_part_of_immutable_content() -> None:
    for column, value in [("game_id", 999), ("game_link_reason", "matched"), ("time_valid", False)]:
        session = retry_session("goalies")
        session.results[2].rows[0][column] = value
        with pytest.raises(ValueError, match="different contents"):
            store_goalies(session)


@pytest.mark.parametrize("valid", [False, True])
def test_injury_foreign_player_links_must_exist_in_nhl(valid: bool) -> None:
    feed = injury_feed()
    links = injury_links(feed)
    links[next(iter(links))] = PlayerLink(12, "matched")
    session = Session([Result(scalar=9), Result(values=[12] if valid else []), Result()])
    if valid:
        assert store_injuries(session, feed, links) == 9
    else:
        with pytest.raises(ValueError, match="existing NHL players"):
            store_injuries(session, feed, links)
        assert session.rollbacks == 1
        assert len(session.calls) == 2
    assert "sport = 'nhl'" in session.calls[1][0] and "FOR SHARE" in session.calls[1][0]


@pytest.mark.parametrize("bad", ["player", "game", None])
def test_goalie_foreign_links_are_nhl_goalies_and_reg_or_pst_games(bad: str | None) -> None:
    feed = goalie_feed()
    links, games = goalie_links(feed), game_links(feed)
    links[next(iter(links))] = PlayerLink(12, "matched")
    games[next(iter(games))] = EventLink(20, "matched")
    session = Session([Result(scalar=9), Result(values=[] if bad == "player" else [12]),
                       Result(values=[] if bad == "game" else [20]), Result()])
    if bad:
        with pytest.raises(ValueError, match="existing NHL"):
            store_goalies(session, feed, links, games)
        assert session.rollbacks == 1
    else:
        assert store_goalies(session, feed, links, games) == 9
    assert "position = 'G'" in session.calls[1][0]
    if bad != "player":
        assert "game_type IN ('REG', 'PST')" in session.calls[2][0]


def test_coverage_and_duplicate_errors_happen_before_sql() -> None:
    feed = injury_feed()
    for links in [{}, {**injury_links(feed), ("99", "99"): PlayerLink(None, "no_candidate")}]:
        session = Session()
        with pytest.raises(ValueError, match="cover source entries exactly"):
            store_injuries(session, feed, links)
        assert not session.calls
    duplicate = replace(feed, injuries=(*feed.injuries, feed.injuries[0]))
    with pytest.raises(ValueError, match="duplicate"):
        store_injuries(Session(), duplicate)


@pytest.mark.parametrize("field", ["fetched", "source", "entry"])
def test_naive_times_are_rejected_before_sql(field: str) -> None:
    feed, fetched = injury_feed(), FETCHED
    if field == "fetched":
        fetched = FETCHED.replace(tzinfo=None)
    elif field == "source":
        feed = replace(feed, source_timestamp=FETCHED.replace(tzinfo=None))
    else:
        feed = replace(feed, injuries=(replace(feed.injuries[0], source_updated_at=FETCHED.replace(tzinfo=None)),))
    with pytest.raises(ValueError, match="timezone-aware"):
        store_injuries(Session(), feed, fetched=fetched)


@pytest.mark.parametrize("link", [
    PlayerLink(None, "matched"), PlayerLink(12, "no_candidate"), PlayerLink(True, "matched"),
    PlayerLink(0, "matched"), PlayerLink(-1, "matched"), PlayerLink(None, "not_reported"),
])
def test_inconsistent_player_links_are_rejected_before_sql(link: PlayerLink) -> None:
    feed = injury_feed()
    links = injury_links(feed)
    links[next(iter(links))] = link
    with pytest.raises(ValueError):
        store_injuries(Session(), feed, links)


def test_source_team_mismatch_cannot_be_linked_despite_existing_player_id() -> None:
    feed = injury_feed()
    feed = replace(feed, injuries=(replace(feed.injuries[0], athlete_team_id="4"),))
    with pytest.raises(ValueError, match="source identity contradicts"):
        store_injuries(Session(), feed, {next(iter(injury_links(feed))): PlayerLink(12, "matched")})


def test_goalie_batch_rejects_missing_game_links_scope_and_partial_events() -> None:
    feed = goalie_feed()
    with pytest.raises(ValueError, match="cover source events exactly"):
        store_goalies(Session(), feed, games={})
    with pytest.raises(ValueError, match="scope date"):
        store_goalies(Session(), replace(feed, scope_date=date(2026, 10, 25)))
    with pytest.raises(ValueError, match="both consistent competitors"):
        store_goalies(Session(), replace(feed, observations=feed.observations[1:]))


def test_unknown_start_and_source_non_goalie_cannot_have_links() -> None:
    feed = goalie_feed()
    first, *others = feed.observations
    invalid_time = replace(feed, observations=(replace(first, time_valid=False), *others))
    games = game_links(feed)
    games[first.espn_event_id] = EventLink(20, "matched")
    with pytest.raises(ValueError, match="unknown event start"):
        store_goalies(Session(), invalid_time, games=games)
    non_goalie = replace(feed, observations=(replace(first, source_position="C"), *others))
    links = goalie_links(feed)
    links[(first.espn_event_id, first.espn_team_id)] = PlayerLink(12, "matched")
    with pytest.raises(ValueError, match="source identity contradicts"):
        store_goalies(Session(), non_goalie, links)


def test_not_reported_competitor_is_stored_without_a_fake_player() -> None:
    feed = goalie_feed()
    first, *others = feed.observations
    first = replace(first, espn_athlete_id=None, player_name=None, status="not_reported",
                    raw_status=None, athlete_team_id=None, source_position=None)
    feed = replace(feed, observations=(first, *others))
    links = goalie_links(feed)
    links[(first.espn_event_id, first.espn_team_id)] = PlayerLink(None, "not_reported")
    session = Session([Result(scalar=9), Result()])
    assert store_goalies(session, feed, links) == 9
    rows = cast(list[dict[str, object]], session.calls[1][1])
    assert rows[0]["player_id"] is None and rows[0]["player_link_reason"] == "not_reported"


def test_dry_run_transaction_is_read_only_with_bounded_statements() -> None:
    session = Session([Result(), Result()])
    asyncio.run(repo.prepare_dry_run(cast(AsyncSession, session)))
    assert [sql for sql, _ in session.calls] == ["SET TRANSACTION READ ONLY", "SET LOCAL statement_timeout = '15s'"]


def test_game_candidate_query_is_scoped_and_includes_adjacent_date_boundaries() -> None:
    row = {"game_id": 10, "sport": "nhl", "game_type": "REG", "start_utc": FETCHED,
           "away_team": "TBL", "home_team": "UTA"}
    session = Session([Result(rows=[row])])
    games = asyncio.run(repo.get_context_games(cast(AsyncSession, session), date(2026, 10, 24)))
    assert len(games) == 1 and games[0].game_id == 10
    sql, params = session.calls[0]
    assert "g.sport = 'nhl'" in sql and "g.game_type IN ('REG', 'PST')" in sql
    assert "away.sport = 'nhl'" in sql and "home.sport = 'nhl'" in sql
    assert params == {"first_date": date(2026, 10, 23), "last_date": date(2026, 10, 25)}
    assert "nhl_context_snapshots" not in sql


def test_player_candidates_reuse_existing_nhl_query(monkeypatch: pytest.MonkeyPatch) -> None:
    query = AsyncMock(return_value=[(12, "Andrei Vasilevskiy", "TBL", "G")])
    monkeypatch.setattr(repo.nhl, "get_player_candidates", query)
    players = asyncio.run(repo.get_context_players(cast(AsyncSession, Session())))
    assert [(row.player_id, row.sport, row.name, row.team, row.position) for row in players] == [
        (12, "nhl", "Andrei Vasilevskiy", "TBL", "G"),
    ]
