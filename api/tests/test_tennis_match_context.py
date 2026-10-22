import asyncio
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.tennis_match_context import WorkloadMatch, completed_sets, return_rate, workload
from app.repositories.matches import Match
from app.repositories.players import PlayerElo, PlayerRollingStats
from app.schemas.tennis import MatchResearchSchema
from app.services.tennis import match_research

DAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 3, 15, tzinfo=timezone.utc)


def row(mid=1, days=1, score="6-4 7-6(5)", status="completed"):
    return WorkloadMatch(mid, DAY - timedelta(days=days), status, score)


@pytest.mark.parametrize("score,count,complete", [
    ("6-4 7-6(5)", 2, True), ("4-6 6-3 8-6", 3, True),
    ("6-2 2-1 RET", 1, False), ("6-4 7-5 RET", 2, False),
    ("6-4 6-7 [10-8]", 2, False), ("6-4 6-7 10-7", 2, False),
    ("0-0", 0, False), (None, 0, False), ("W/O", 0, False),
    ("6:4 6:3", 0, False), ("6-5 7-2", 0, False),
])
def test_sets_are_completed_sets_not_guessed_match_totals(score, count, complete):
    assert completed_sets(score) == (count, complete)


def test_workload_deduplicates_and_excludes_target_future_same_day_and_unplayed():
    rows = [row(), row(), row(2, 7), row(3, 8), row(99), row(4, 0), row(5, -1),
            row(6, status="cancelled"), row(7, score="W/O"), row(8, score="0-0")]
    data = workload(rows, 99, DAY)
    assert data.matches_played == 2
    assert data.completed_sets == 4
    assert data.matches_with_complete_scores == 2
    assert data.previous_match_date == DAY - timedelta(days=1)
    assert data.calendar_days_since_match == 1
    assert data.window_start == DAY - timedelta(days=7)
    assert data.window_end_exclusive == DAY
    assert data.minutes_played is None


def test_workload_partial_scores_and_unknown_scores_have_explicit_coverage():
    data = workload([row(1, score="6-4 2-1 RET"), row(2, score=None)], 99, DAY)
    assert (data.matches_played, data.completed_sets, data.matches_with_complete_scores) == (2, 1, 0)


def test_previous_match_can_be_outside_week_and_missing_history_is_not_zero_rest():
    data = workload([row(days=30)], 99, DAY)
    assert data.matches_played == 0 and data.calendar_days_since_match == 30
    empty = workload([row(days=366)], 99, DAY)
    assert empty.previous_match_date is None and empty.calendar_days_since_match is None


@pytest.mark.parametrize("score", ["W.O.", "W/O", "WO", "Walkover", "0-0 0-0", "DEFAULT"])
def test_unplayed_score_variants_do_not_count(score):
    assert workload([row(score=score)], 99, DAY).matches_played == 0


@pytest.mark.parametrize("value", [None, -.1, 1.1, float("nan"), float("inf")])
def test_return_conversion_rejects_invalid_denominators(value):
    assert return_rate(value) is None


def test_return_conversion_uses_complement_of_opponent_service_points_won():
    assert return_rate(.7) == pytest.approx(.3)
    assert return_rate(0) == 1
    assert return_rate(1) == 0


def stats(surface="Hard", count=5):
    return PlayerRollingStats(1, surface, "last_52w", "overall", "all", .6, .65, .35,
                              .1, .02, .8, .4, count, first_in_pct=.6, first_won_pct=.7,
                              second_won_pct=.5, computed_at=NOW,
                              allowed_first_won_pct=.68, allowed_second_won_pct=.48)


def test_research_preserves_small_surface_samples_timestamps_and_missing_values():
    data = match_research.research_stats(stats())
    assert data.surface == "Hard" and data.matches_count == 5 and data.thin_sample
    assert data.computed_at == NOW
    assert data.first_return_won == pytest.approx(.32)
    assert data.second_return_won == pytest.approx(.52)
    assert data.break_conversion_pct == .4
    assert "not a historical" in data.snapshot_basis
    invalid = match_research.research_stats(replace(stats(), first_won_pct=2, allowed_second_won_pct=None))
    assert invalid.first_serve_won is None and invalid.second_return_won is None
    assert not match_research.research_stats(stats(count=10)).thin_sample
    assert match_research.research_stats(None) is None


def test_service_keeps_overall_separate_and_serializes_nested_current_and_historical_context(monkeypatch):
    async def get_stats(_db, ids, period):
        assert ids == [1, 2] and period == "last_52w"
        return {(1, "Hard"): stats(), (1, None): stats(None, 30), (2, None): replace(stats(None, 20), player_id=2)}

    async def get_history(_db, ids, on):
        assert on == DAY
        return {1: [row()]}

    async def get_odds(_db, mid, before):
        assert mid == 99 and before == NOW
        return [match_research.BookFreshness("DraftKings", NOW - timedelta(hours=1))]

    monkeypatch.setattr(match_research.player_repo, "get_rolling_stats_batch_all_surfaces", get_stats)
    monkeypatch.setattr(match_research.context_repo, "get_workload_matches", get_history)
    monkeypatch.setattr(match_research.context_repo, "get_book_freshness", get_odds)
    match = Match(99, "key", DAY, NOW, "ATP", "Hard", "Lyon", "R16", 3, 1, 2, None, None, 1, "completed", None)
    elo = PlayerElo(1, DAY, 1900, 1850, 1700, 1800)
    data = asyncio.run(match_research.build_match_research(None, match, {1: elo}))
    assert data.players[0].surface_stats.matches_count == 5
    assert data.players[1].surface_stats is None
    assert data.players[1].overall_stats.matches_count == 20
    assert data.players[1].elo_as_of_date is None
    payload = MatchResearchSchema(**asdict(data)).model_dump(by_alias=True, mode="json")
    assert payload["players"][0]["surfaceStats"]["computedAt"] == "2026-10-22T03:15:00Z"
    assert payload["players"][0]["workload"]["windowEndExclusive"] == "2026-10-22"
    assert payload["players"][1]["workload"]["minutesPlayed"] is None
