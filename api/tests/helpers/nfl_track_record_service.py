"""Shared fixtures and builders, first written for `test_nfl_track_record_service.py`."""
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime


from app.backtest.nfl_prizepicks_lines import MoneylineTiming
from app.core.nfl_game_line_clv import ClvMarketGrade, ClvPick
from app.core.nfl_line_grading import GradeableLine, settle_line
from app.core.prop_ranking_rule import FrozenCall
from app.services.nfl.track_record import LineGradingInputs
from app.services.prop_ranking import RankingCalls


GRADED_AT = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _call(i: int, *, week: int = 3, hit: bool = True, p_over: float = 0.9) -> FrozenCall:
    return FrozenCall(
        line_id=i, period=week, player_id=i, game_id=1000 + i, market="receiving_yards", odds_type="standard",
        p_over=p_over, p_under=1 - p_over, outcome="over" if hit else "under",
    )


def _inputs(calls: list[FrozenCall], finished: set[int] | None = None) -> RankingCalls:
    return RankingCalls(
        calls=calls, exclusions=Counter({"void_dnp": 2, "push": 1}), frozen_rows=len(calls) + 3,
        coverage={3: (6087, 5729), 2: (5380, 0)}, finished_periods=finished if finished is not None else {3, 2},
    )


def _clv_pick(i: int, week: int, clv: float) -> ClvPick:
    # A total where the model sits 4 points over the entry line, so CLV is simply close minus entry.
    return ClvPick(f"g{week}_{i}", week, "total", 44.0, 40.0, 40.0 + clv, 45)


def _grade(picks: list[ClvPick], lead_hours: list[float] | None = None) -> ClvMarketGrade:
    return ClvMarketGrade("total", len(picks) + 2, picks, Counter({"no entry line": 3}), lead_hours or [])


FETCHED = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)


def _line(line_id: int, **overrides: object) -> GradeableLine:
    base = GradeableLine(
        line_id=line_id, season=2026, week=2, game_id=3, player_id=line_id, market="receptions",
        segment="full_game", odds_type="standard", line=4.5, fetched_at=FETCHED,
        stat_value=6.0, offense_snaps=50, game_has_stats=True,
    )
    return replace(base, **overrides)


def _line_inputs(lines: list[GradeableLine], edges: dict[int, float], p_overs: dict[int, float] | None = None):
    return LineGradingInputs(
        [settle_line(line) for line in lines], edges, p_overs or {}, MoneylineTiming(0, 0),
    )
