from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.projection_history import latest_line_per_match


@dataclass(frozen=True)
class Row:
    snapshot_id: int
    match_id: int
    stat_type: str
    snapshot_at: datetime
    line: float = 7.5


def at(day: int) -> datetime:
    return datetime(2026, 10, day, 12, tzinfo=timezone.utc)


def test_a_single_line_is_kept():
    row = Row(1, 10, "Aces", at(1))
    assert latest_line_per_match([row]) == [row]


def test_a_moved_line_keeps_the_later_snapshot():
    early, late = Row(1, 10, "Aces", at(1), 6.5), Row(2, 10, "Aces", at(2), 7.5)
    assert latest_line_per_match([late, early]) == [late]


def test_a_tie_on_snapshot_time_keeps_the_higher_id():
    low, high = Row(3, 10, "Aces", at(1), 6.5), Row(4, 10, "Aces", at(1), 7.5)
    assert latest_line_per_match([high, low]) == [high]


def test_two_stats_on_one_match_stay_apart():
    aces, faults = Row(1, 10, "Aces", at(1)), Row(2, 10, "Double Faults", at(1))
    assert latest_line_per_match([aces, faults]) == [aces, faults]


def test_stat_spellings_that_normalize_together_are_one_stat():
    spaced, snake = Row(1, 10, "Double Faults", at(1)), Row(2, 10, "double_faults", at(2))
    assert latest_line_per_match([spaced, snake]) == [snake]


def test_empty_input_is_empty():
    assert latest_line_per_match([]) == []


from datetime import date  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.box_score_join import BoxScoreCandidate, JoinResult  # noqa: E402
from app.core.projection_history import ProjectionHistoryPoint, history_point  # noqa: E402
from app.db.pool import get_db  # noqa: E402
from app.repositories.prop_snapshots import ProjectionHistorySnapshot  # noqa: E402
from app.routers import tennis as tennis_router  # noqa: E402
from app.services.tennis.projection_history import ProjectionHistory  # noqa: E402


def snapshot(stat_type: str, score: str | None = "6-4 6-3", projection: float | None = 8.1, **kw) -> ProjectionHistorySnapshot:
    fields = dict(
        snapshot_id=1, match_id=10, stat_type=stat_type, line=7.5, projection=projection, snapshot_at=at(1),
        player_is_p1=True, score=score, best_of=3, match_date=date(2026, 10, 2), tournament="Shanghai",
        round="R32", surface="Hard", opponent_id=40, opponent_name="Ben Shelton",
    )
    return ProjectionHistorySnapshot(**{**fields, **kw})


def joined(aces: int | None) -> JoinResult:
    box = BoxScoreCandidate(1, date(2026, 10, 2), "W", "Ben Shelton", "6-4 6-3", aces, 2, 3)
    return JoinResult(box, "joined")


def test_a_score_stat_settles_from_the_score():
    point = history_point(snapshot("Total Games"), None)
    assert point is not None and point.stat == "total_games" and point.actual == 19
    assert (point.line, point.projection, point.opponent_name) == (7.5, 8.1, "Ben Shelton")


def test_a_score_stat_reads_from_the_players_side():
    point = history_point(snapshot("Total Games Won", player_is_p1=False), None)
    assert point is not None and point.actual == 7


def test_a_box_score_stat_settles_from_the_join():
    point = history_point(snapshot("Aces"), joined(9))
    assert point is not None and point.actual == 9


def test_a_box_score_stat_without_a_join_is_unsettled():
    point = history_point(snapshot("Aces"), None)
    assert point is not None and point.actual is None
    missed = history_point(snapshot("Aces"), JoinResult(None, "score_mismatch"))
    assert missed is not None and missed.actual is None


def test_a_retired_match_is_void():
    assert history_point(snapshot("Total Games", score="6-4 3-1"), None) is None
    assert history_point(snapshot("Total Games", score=None), None) is None


def test_a_missing_projection_stays_missing_and_the_result_still_settles():
    point = history_point(snapshot("Total Games", projection=None), None)
    assert point is not None and point.projection is None and point.actual == 19


def test_fantasy_score_has_no_settlement_source():
    point = history_point(snapshot("Fantasy Score"), None)
    assert point is not None and point.actual is None


def _client(monkeypatch, history):
    async def build(_db, player_id):
        return history if player_id == 26 else None

    monkeypatch.setattr(tennis_router, "build_projection_history", build)
    app = FastAPI()
    app.include_router(tennis_router.router, prefix="/tennis")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_route_serializes_in_camel_case(monkeypatch):
    point = ProjectionHistoryPoint(10, date(2026, 10, 2), "Shanghai", "R32", "Hard", 40, "Ben Shelton",
                                   "aces", 7.5, None, 9, at(1))
    res = _client(monkeypatch, ProjectionHistory("props-v3", [point], 2)).get("/tennis/players/26/projection-history")
    assert res.status_code == 200
    body = res.json()
    assert (body["projectionVersion"], body["unsettled"]) == ("props-v3", 2)
    assert body["points"][0]["opponentName"] == "Ben Shelton"
    assert body["points"][0]["projection"] is None and body["points"][0]["matchDate"] == "2026-10-02"


def test_route_404s_an_unknown_player(monkeypatch):
    res = _client(monkeypatch, ProjectionHistory("props-v3", [], 0)).get("/tennis/players/404/projection-history")
    assert res.status_code == 404
