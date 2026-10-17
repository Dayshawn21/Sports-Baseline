from __future__ import annotations

import datetime as dt
from dataclasses import replace

from app.core.nba_slate_gaps import DIGEST_LIMIT, GapCandidate, rank_slate_gaps

NOW = dt.datetime(2026, 10, 20, 18, 0, tzinfo=dt.UTC)
TIP = NOW + dt.timedelta(hours=5)


def candidate(player_id: int = 1, *, line: float = 20.5, projection: float | None = 22.5, **changes: object) -> GapCandidate:
    base = GapCandidate(
        game_id=10, start_utc=TIP, status="scheduled", player_id=player_id, player_name=f"Player {player_id}",
        market="points", odds_type="standard", line=line, projection=projection,
        gap=None if projection is None else projection - line,
    )
    return replace(base, **changes)


def ranked_ids(candidates: list[GapCandidate]) -> list[int]:
    return [item.candidate.player_id for item in rank_slate_gaps(candidates, NOW)]


def test_only_standard_lines_with_a_projection_qualify():
    lines = [
        candidate(1),
        candidate(2, odds_type="goblin"),
        candidate(3, odds_type="demon"),
        candidate(4, odds_type=None),
        candidate(5, projection=None),
    ]
    assert ranked_ids(lines) == [1]


def test_started_and_unscheduled_games_are_dropped():
    lines = [
        candidate(1),
        candidate(2, start_utc=NOW),
        candidate(3, start_utc=NOW - dt.timedelta(minutes=1)),
        candidate(4, start_utc=None),
        candidate(5, status="completed"),
        candidate(6, status="postponed"),
    ]
    assert ranked_ids(lines) == [1]


def test_ranks_by_gap_share_of_the_line_not_raw_gap():
    small_line = candidate(1, line=4.5, projection=6.5)
    big_line = candidate(2, line=25.5, projection=29.5)
    under = candidate(3, line=10.5, projection=7.5)
    result = rank_slate_gaps([big_line, small_line, under], NOW)
    assert [item.candidate.player_id for item in result] == [1, 3, 2]
    assert result[0].gap_share == 2.0 / 4.5
    assert result[1].gap_share == 3.0 / 10.5


def test_one_line_per_player_keeps_the_top_ranked():
    lines = [
        candidate(1, market="points", line=20.5, projection=21.5),
        candidate(1, market="assists", line=4.5, projection=6.5),
        candidate(2, line=20.5, projection=22.5),
    ]
    result = rank_slate_gaps(lines, NOW)
    assert [(item.candidate.player_id, item.candidate.market) for item in result] == [(1, "assists"), (2, "points")]


def test_ties_break_on_name_then_market_then_game():
    lines = [
        candidate(1, player_name="Bravo"),
        candidate(2, player_name="Alpha", market="rebounds", game_id=11),
        candidate(3, player_name="Alpha", market="points", game_id=12),
        candidate(4, player_name="Alpha", market="points", game_id=11),
    ]
    assert ranked_ids(lines) == [4, 3, 2, 1]


def test_limit_caps_the_digest():
    lines = [candidate(player_id, projection=20.5 + player_id) for player_id in range(1, 8)]
    assert ranked_ids(lines) == [7, 6, 5, 4]
    assert len(ranked_ids(lines)) == DIGEST_LIMIT
    assert [item.candidate.player_id for item in rank_slate_gaps(lines, NOW, limit=2)] == [7, 6]


def test_no_qualifying_line_gives_an_empty_digest():
    assert rank_slate_gaps([], NOW) == []
    assert rank_slate_gaps([candidate(1, odds_type="goblin")], NOW) == []
