import asyncio
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.tennis_player import EloSnapshot
from app.db.pool import get_db
from app.repositories.matches import NextMatch, get_latest_rank, get_next_match
from app.repositories.players import PlayerHeader, get_elo_tour_rank
from app.routers import tennis as tennis_router
from app.services.tennis import player_detail

TODAY = date(2026, 9, 29)
HEADER = PlayerHeader(26, "Jakub Mensik", "ATP", "R", "CZE", date(2005, 9, 30))
HISTORY = [
    EloSnapshot(date(2026, 1, 5), 1878.0, 1890.0, None, None),
    EloSnapshot(date(2026, 8, 24), 1942.0, 1968.0, 1881.0, 1903.0),
]
NEXT = NextMatch(501, datetime(2026, 9, 29, 10, 30, tzinfo=timezone.utc), TODAY, "Tokyo", "R16", "Hard", 40, "Ben Shelton")


class _Result:
    def __init__(self, row=None, rows=None, scalar=None):
        self._row, self._rows, self._scalar = row, rows or [], scalar

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar


class _Db:
    def __init__(self, result):
        self.result = result
        self.sql = ""
        self.params = None

    async def execute(self, sql, params):
        self.sql, self.params = str(sql), params
        return self.result


def _patch(monkeypatch, *, header=HEADER, history=HISTORY, next_match=NEXT):
    calls = {}

    async def get_header(_db, pid):
        return header if pid == 26 else None

    async def get_history(_db, _pid):
        return history

    async def get_rank(_db, pid, tour, as_of):
        calls["tour_rank"] = (pid, tour, as_of)
        return 17, 312

    async def aliases(_db, _pid):
        return ["Jakub Mensik"]

    async def computed_at(_db, _pid):
        return datetime(2026, 9, 29, 11, 12, tzinfo=timezone.utc)

    async def latest_rank(_db, _pid):
        return 19

    async def next_fake(_db, _pid, today):
        calls["today"] = today
        return next_match

    monkeypatch.setattr(player_detail.player_repo, "get_player_header", get_header)
    monkeypatch.setattr(player_detail.player_repo, "get_elo_history", get_history)
    monkeypatch.setattr(player_detail.player_repo, "get_elo_tour_rank", get_rank)
    monkeypatch.setattr(player_detail.player_repo, "get_player_aliases", aliases)
    monkeypatch.setattr(player_detail.player_repo, "get_rolling_stats_computed_at", computed_at)
    monkeypatch.setattr(player_detail.match_repo, "get_latest_rank", latest_rank)
    monkeypatch.setattr(player_detail.match_repo, "get_next_match", next_fake)
    return calls


def test_detail_assembles_the_profile(monkeypatch):
    calls = _patch(monkeypatch)

    detail = asyncio.run(player_detail.build_player_detail(None, 26, TODAY))

    assert detail.header.name == "Jakub Mensik"
    assert detail.rank == 19
    assert detail.elo.summary.latest.overall == 1942.0
    assert detail.elo.summary.change == 64.0
    assert (detail.elo.tour_rank, detail.elo.tour_rank_of) == (17, 312)
    assert calls["tour_rank"] == (26, "ATP", date(2026, 8, 24))
    assert calls["today"] == TODAY
    assert detail.next_match.opponent_name == "Ben Shelton"


def test_detail_without_elo_skips_the_tour_rank(monkeypatch):
    calls = _patch(monkeypatch, history=[], next_match=None)

    detail = asyncio.run(player_detail.build_player_detail(None, 26, TODAY))

    assert detail.elo.summary.latest is None
    assert detail.elo.tour_rank is None
    assert "tour_rank" not in calls
    assert detail.next_match is None


def test_unknown_player_is_none(monkeypatch):
    _patch(monkeypatch)

    assert asyncio.run(player_detail.build_player_detail(None, 404, TODAY)) is None


def test_tour_rank_counts_strictly_higher_so_ties_share():
    db = _Db(_Result(row=(17, 312)))

    rank = asyncio.run(get_elo_tour_rank(db, 26, "ATP", date(2026, 8, 24)))

    assert rank == (17, 312)
    assert "1 + COUNT(*) FILTER (WHERE e.elo > (SELECT elo FROM mine))" in db.sql
    assert "p.tour = :tour" in db.sql
    assert db.params == {"id": 26, "tour": "ATP", "as_of": date(2026, 8, 24)}


def test_next_match_puts_a_live_match_first():
    db = _Db(_Result(row=None))

    assert asyncio.run(get_next_match(db, 26, TODAY)) is None
    assert "ORDER BY (m.status = 'live') DESC, m.start_utc NULLS LAST, m.id" in db.sql
    assert "m.status = 'scheduled' AND m.match_date >= :today" in db.sql


def test_latest_rank_reads_the_players_own_side():
    db = _Db(_Result(scalar=19))

    assert asyncio.run(get_latest_rank(db, 26)) == 19
    assert "CASE WHEN p1_id = :pid THEN p1_rank ELSE p2_rank END" in db.sql


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tennis_router.router, prefix="/tennis")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_route_serializes_in_camel_case(monkeypatch):
    _patch(monkeypatch)

    res = _client().get("/tennis/players/26")

    assert res.status_code == 200
    body = res.json()
    assert body["birthDate"] == "2005-09-30"
    assert body["elo"]["tourRank"] == 17
    assert body["elo"]["history"][0]["asOf"] == "2026-01-05"
    assert body["nextMatch"]["opponentId"] == 40
    assert body["statsComputedAt"].startswith("2026-09-29T11:12")


def test_route_404s_an_unknown_player(monkeypatch):
    _patch(monkeypatch)

    assert _client().get("/tennis/players/404").status_code == 404


def test_a_non_numeric_id_does_not_match_the_player_route(monkeypatch):
    _patch(monkeypatch)

    # "stats" and "compare" are sibling routes; the :int converter keeps them reachable.
    assert _client().get("/tennis/players/abc").status_code == 404


from app.core.tennis_player import ServeReturnStats  # noqa: E402
from app.repositories.players import SurfaceServeReturnRow  # noqa: E402


def _row(pid, surface, matches, hold):
    return SurfaceServeReturnRow(pid, surface, matches, ServeReturnStats(hold_pct=hold, aces_per_game=0.1))


def test_serve_return_compares_each_surface_to_the_tour():
    rows = [
        _row(26, None, 58, 0.88), _row(2, None, 40, 0.80), _row(3, None, 5, 0.10),
        _row(26, "Hard", 43, 0.90), _row(2, "Hard", 30, 0.70),
        _row(2, "Grass", 12, 0.85),
    ]

    result = player_detail.compare_serve_return(26, "ATP", rows)
    by_surface = {s.surface: s for s in result.surfaces}

    assert list(by_surface) == ["all", "Hard", "Clay", "Grass"]
    # Player 3's 5 matches fall under the floor; the player's own row counts toward the tour.
    assert by_surface["all"].tour_average.players == 2
    assert by_surface["all"].tour_average.stats.hold_pct == pytest.approx(0.84)
    assert by_surface["Hard"].player_matches == 43
    assert by_surface["Hard"].player.hold_pct == 0.90


def test_a_surface_without_the_player_keeps_the_tour_average():
    result = player_detail.compare_serve_return(26, "ATP", [_row(2, "Grass", 12, 0.85)])
    grass = next(s for s in result.surfaces if s.surface == "Grass")
    clay = next(s for s in result.surfaces if s.surface == "Clay")

    assert grass.player is None and grass.player_matches is None
    assert grass.tour_average.players == 1
    assert clay.tour_average.players == 0
    assert clay.tour_average.stats.hold_pct is None


def test_serve_return_route(monkeypatch):
    _patch(monkeypatch)

    async def rows(_db, tour):
        assert tour == "ATP"
        return [_row(26, "Hard", 43, 0.90), _row(2, "Hard", 30, 0.70)]

    monkeypatch.setattr(player_detail.player_repo, "get_tour_serve_return_rows", rows)
    client = _client()

    body = client.get("/tennis/players/26/serve-return").json()
    hard = next(s for s in body["surfaces"] if s["surface"] == "Hard")

    assert hard["player"]["matches"] == 43
    assert hard["player"]["holdPct"] == 0.90
    assert hard["tourAverage"]["players"] == 2
    assert body["surfaces"][0]["player"] is None
    assert client.get("/tennis/players/404/serve-return").status_code == 404


from app.core.box_score_join import BoxScoreCandidate, JoinResult  # noqa: E402
from app.repositories.matches import PlayerMatchLogRow, get_player_matches  # noqa: E402

LOG_ROW = (81689, date(2026, 9, 25), "Tokyo", "R32", "Hard", 3, 40, "Arthur Fils", 14, True)


def test_player_matches_flip_a_p2_score_to_the_players_side():
    db = _Db(_Result(rows=[LOG_ROW + ("6-7 4-6", True), LOG_ROW + ("7-6 6-4", False)]))

    rows = asyncio.run(get_player_matches(db, 26, limit=20))

    assert [r.score for r in rows] == ["7-6 6-4", "7-6 6-4"]
    assert rows[0].opponent_rank == 14 and rows[0].won is True
    assert "ORDER BY m.match_date DESC, m.id DESC" in db.sql
    assert db.params == {"pid": 26, "limit": 20, "since": None}


def _log_row(match_id):
    return PlayerMatchLogRow(match_id, date(2026, 9, 25), "Tokyo", "R32", "Hard", 3, 40, "Arthur Fils", 14, True, "7-6 6-4")


class _Context:
    def __init__(self, candidate):
        self.candidate = candidate

    def join(self):
        return JoinResult(self.candidate, "joined" if self.candidate else "no_candidate")


def _patch_log(monkeypatch, contexts):
    _patch(monkeypatch)

    async def matches(_db, _pid, *, limit=None, since=None):
        return [_log_row(1), _log_row(2)][:limit]

    async def candidates(_db, pairs, *, sources):
        assert sources == ("tennisabstract", "tennismylife")
        return {pair: ctx for pair, ctx in contexts.items() if pair in pairs}

    monkeypatch.setattr(player_detail.match_repo, "get_player_matches", matches)
    monkeypatch.setattr(player_detail.box_score_repo, "get_box_score_candidates", candidates)


BOX = BoxScoreCandidate(9, date(2026, 9, 22), "W", "Arthur Fils", "7-6 6-4", 14, 2, 1, 4,
                        break_points_faced=3, break_points_saved=3)


def test_match_log_attaches_joined_box_scores_and_leaves_misses_empty(monkeypatch):
    _patch_log(monkeypatch, {(26, 1): _Context(BOX), (26, 2): _Context(None)})

    log = asyncio.run(player_detail.build_player_matches(None, 26, 20, TODAY)).log

    assert log[0].box is BOX
    assert log[1].box is None
    assert asyncio.run(player_detail.build_player_matches(None, 404, 20, TODAY)) is None


def test_the_record_reads_the_whole_window_not_the_capped_log(monkeypatch):
    _patch_log(monkeypatch, {})
    seen = {}

    async def matches(_db, _pid, *, limit=None, since=None):
        seen.setdefault("calls", []).append((limit, since))
        return [_log_row(1), _log_row(2)][:limit]

    monkeypatch.setattr(player_detail.match_repo, "get_player_matches", matches)

    result = asyncio.run(player_detail.build_player_matches(None, 26, 1, TODAY))

    assert len(result.log) == 1
    assert (result.record.all.wins, result.record.all.losses) == (2, 0)
    assert (None, date(2025, 9, 29)) in seen["calls"]


def test_matches_route_maps_box_fields_and_bounds_the_limit(monkeypatch):
    _patch_log(monkeypatch, {(26, 1): _Context(BOX)})
    client = _client()

    body = client.get("/tennis/players/26/matches").json()
    first, second = body["log"]

    assert (first["result"], first["opponentRank"], first["aces"]) == ("W", 14, 14)
    assert (first["bpSaved"], first["bpFaced"], first["bpWon"], first["bpCreated"]) == (3, 3, 1, 4)
    assert second["aces"] is None and second["bpSaved"] is None
    # The route dates the window from the real clock; the counts are tested with a fixed day above.
    assert set(body["record"]["all"]) == {"wins", "losses"}
    assert set(body["record"]) == {"windowStart", "all", "hard", "clay", "grass", "vsTop20", "decidingSets", "tieBreaks"}
    assert client.get("/tennis/players/26/matches", params={"limit": 0}).status_code == 422
    assert client.get("/tennis/players/26/matches", params={"limit": 51}).status_code == 422
    assert len(client.get("/tennis/players/26/matches", params={"limit": 1}).json()["log"]) == 1
    assert client.get("/tennis/players/404/matches").status_code == 404


from app.repositories.prop_snapshots import GradedPropSnapshot  # noqa: E402

SNAP_AT = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)


def _snap(i, *, stat="Total Games", line=19.5, rec="UNDER", odds_type="standard", score="6-4 6-3"):
    return GradedPropSnapshot(
        snapshot_id=i, player_id=26, match_id=900 + i, tour="ATP", stat_type=stat, odds_type=odds_type,
        line=line, recommendation=rec, confidence="LEAN", hit_probability=0.6, player_is_p1=True,
        score=score, best_of=3, snapshot_at=SNAP_AT,
    )


def test_each_past_prop_outcome():
    joined = JoinResult(BOX, "joined")
    cases = {
        "hit": player_detail.past_prop(_snap(1), None),                      # 19 games under 19.5
        "miss": player_detail.past_prop(_snap(2, rec="OVER"), None),
        "push": player_detail.past_prop(_snap(3, line=19.0), None),
        "pass": player_detail.past_prop(_snap(4, rec=None), None),
        "void": player_detail.past_prop(_snap(5, score="6-4 2-1"), None),     # retirement
        "awaiting": player_detail.past_prop(_snap(6, stat="Aces", line=10.5), None),
        "ungradable": player_detail.past_prop(_snap(8, stat="Fantasy Score", line=11.5), None),
    }

    assert {name: p.outcome for name, p in cases.items()} == {name: name for name in cases}
    assert cases["hit"].actual == 19 and cases["hit"].stat == "total_games"
    assert cases["void"].actual is None
    aces = player_detail.past_prop(_snap(7, stat="Aces", line=10.5, rec="OVER"), joined)
    assert (aces.actual, aces.outcome) == (14, "hit")
    assert cases["hit"].snapshot_date == date(2026, 9, 25)


def _patch_props(monkeypatch, snapshots):
    _patch(monkeypatch)
    seen = {}

    async def graded(_db, version, player_id=None):
        seen["args"] = (version, player_id)
        return snapshots

    async def candidates(_db, _pairs, *, sources):
        assert sources == ("tennisabstract", "tennismylife")
        return {}

    monkeypatch.setattr(player_detail.prop_snapshot_repo, "get_graded_prop_snapshots", graded)
    monkeypatch.setattr(player_detail.box_score_repo, "get_box_score_candidates", candidates)
    return seen


def test_the_summary_counts_standard_lines_with_a_pick_only(monkeypatch):
    seen = _patch_props(monkeypatch, [
        _snap(1), _snap(2, rec="OVER"), _snap(3, rec="OVER"),
        _snap(4, odds_type="goblin", line=17.5, rec="OVER"),
        _snap(5, rec=None), _snap(6, line=19.0),
    ])

    props = asyncio.run(player_detail.build_player_props(None, 26))

    assert seen["args"] == ("props-v3", 26)
    assert (props.hits, props.misses) == (1, 2)
    assert len(props.rows) == 6


def test_a_player_without_snapshots_gets_an_empty_list(monkeypatch):
    _patch_props(monkeypatch, [])

    props = asyncio.run(player_detail.build_player_props(None, 26))

    assert props.rows == [] and (props.hits, props.misses) == (0, 0)
    assert asyncio.run(player_detail.build_player_props(None, 404)) is None


def test_props_route(monkeypatch):
    _patch_props(monkeypatch, [_snap(1)])

    body = _client().get("/tennis/players/26/props").json()

    assert body["projectionVersion"] == "props-v3"
    assert body["rows"][0] == {
        "snapshotDate": "2026-09-25", "stat": "total_games", "oddsType": "standard", "line": 19.5,
        "actual": 19, "recommendation": "UNDER", "confidence": "LEAN", "outcome": "hit",
    }
    assert body["summary"] == {"hits": 1, "misses": 0}
    assert _client().get("/tennis/players/404/props").status_code == 404


def test_slate_predictions_carry_player_ids_for_links():
    from app.services.tennis.predictor import PredictionOutput

    output = PredictionOutput(
        match_id=7, start_utc=None, p1_name="Jakub Mensik", p2_name="Ben Shelton", tour="ATP",
        surface="Hard", tournament="Tokyo", round="R16", p1_win_prob=0.5, p2_win_prob=0.5,
        p1_elo_prob=None, p1_ml_prob=None, p1_market_prob=None, ensemble_weights={}, quality_flags=[],
        p1_odds_american=None, p2_odds_american=None, h2h_p1_wins=0, h2h_p2_wins=0, p1_id=26, p2_id=40,
    )

    body = tennis_router._to_schema(output).model_dump(by_alias=True)

    assert (body["p1Id"], body["p2Id"]) == (26, 40)
