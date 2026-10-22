from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.core.nfl_matchup_context import (
    ALLOWED_MEASURES, ContextCutoff, HistoryGame, PlayerUsageGame,
    TeamAllowedGame, eligible_game, player_usage, position_allowed,
)
from app.schemas.nfl import (
    NflGameContextResponse, NflMatchupContextSchema, NflMatchupTeamSchema,
    NflContextPlayerSchema, NflPositionAllowedSchema, NflUsageWindowSchema,
)

CUTOFF = ContextCutoff(2026, 7, datetime(2026, 10, 25, 17, tzinfo=UTC))


def game(week: int) -> HistoryGame:
    return HistoryGame(week, 2026, week, datetime(2026, 9, week, 17, tzinfo=UTC))


@pytest.mark.parametrize("changed", [
    {"season": 2025}, {"week": 7}, {"week": 8}, {"week": 0},
    {"game_type": "PRE"}, {"game_type": "POST"}, {"completed": False},
    {"sport": "nba"}, {"start_utc": None},
    {"start_utc": datetime(2026, 9, 1)},
    {"start_utc": CUTOFF.kickoff},
    {"start_utc": datetime(2026, 11, 1, tzinfo=UTC)},
])
def test_uniform_pre_week_cutoff(changed: dict) -> None:
    excluded = replace(game(1), **changed)
    assert not eligible_game(excluded, CUTOFF)
    assert eligible_game(game(1), CUTOFF)
    usage = player_usage([PlayerUsageGame(excluded, "A", targets=100)], CUTOFF)
    assert usage.season_usage.targets.value is None
    assert usage.season_usage.targets.eligible_games == 0
    allowed = position_allowed([TeamAllowedGame(excluded, 1, rb_carries=100)], [1], CUTOFF)
    assert allowed[1]["rb_carries"].value is None


def test_recent_selected_before_metric_filtering_byes_and_dnps() -> None:
    rows = [
        PlayerUsageGame(game(1), "A", targets=20),
        PlayerUsageGame(game(2), "A", targets=6),
        PlayerUsageGame(game(4), "A", targets=0),
        PlayerUsageGame(game(5), "A", targets=99, played=False),
        PlayerUsageGame(game(6), "A", targets=None),
    ]
    usage = player_usage(reversed(rows), CUTOFF)
    recent, season = usage.recent_usage.targets, usage.season_usage.targets
    assert (recent.value, recent.observed_games, recent.eligible_games) == (3, 2, 3)
    assert (recent.window_start, recent.window_end) == (date(2026, 9, 2), date(2026, 9, 4))
    assert (season.value, season.observed_games, season.eligible_games) == (26 / 3, 3, 4)


def test_shares_pair_actual_team_totals_across_trade_and_missing_metrics() -> None:
    usage = player_usage([
        PlayerUsageGame(game(1), "OLD", targets=2, team_targets=10, carries=4, team_carries=10),
        PlayerUsageGame(game(3), "NEW", targets=9, team_targets=30, carries=6, team_carries=30),
        PlayerUsageGame(game(5), "NEW", targets=5, team_targets=None, carries=None, team_carries=20),
        PlayerUsageGame(game(6), "NEW", targets=None, team_targets=40, carries=0, team_carries=0),
    ], CUTOFF)
    season, recent = usage.season_usage, usage.recent_usage
    assert season.teams == ("OLD", "NEW")
    assert season.target_share.value == pytest.approx(11 / 40)
    assert season.carry_share.value == pytest.approx(10 / 40)
    assert season.target_share.observed_games == season.carry_share.observed_games == 2
    assert season.target_share.eligible_games == 4
    assert season.target_share.window_end == date(2026, 9, 3)
    assert recent.target_share.value == pytest.approx(9 / 30)
    assert recent.carry_share.value == pytest.approx(6 / 30)
    assert recent.target_share.eligible_games == 3


def test_snap_share_is_mean_of_stored_fractions_with_own_sample() -> None:
    usage = player_usage([
        PlayerUsageGame(game(1), "A", offense_pct=0.8),
        PlayerUsageGame(game(2), "A", offense_pct=0.4),
        PlayerUsageGame(game(3), "A", offense_pct=None),
        PlayerUsageGame(game(4), "A", offense_pct=0),
    ], CUTOFF)
    assert usage.season_usage.avg_game_snap_share.value == pytest.approx(0.4)
    snap = usage.recent_usage.avg_game_snap_share
    assert (snap.value, snap.observed_games, snap.eligible_games) == (0.2, 2, 3)
    assert (snap.window_start, snap.window_end) == (date(2026, 9, 2), date(2026, 9, 4))


def test_observed_zero_missing_and_zero_denominator_are_distinct() -> None:
    row = PlayerUsageGame(game(1), "A", targets=0, team_targets=20, carries=0, team_carries=0)
    usage = player_usage([row], CUTOFF).season_usage
    assert usage.targets.value == usage.target_share.value == usage.carries.value == 0
    assert usage.target_share.reason is None
    assert usage.carry_share.value is None
    assert usage.carry_share.reason == "zero_denominator"
    assert usage.carry_share.observed_games == 0
    assert usage.carry_share.window_start is None
    assert usage.avg_game_snap_share.reason == "missing_data"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -1])
def test_invalid_usage_values_are_unavailable(invalid: float) -> None:
    usage = player_usage([
        PlayerUsageGame(game(1), "A", targets=invalid, team_targets=10, offense_pct=invalid),
    ], CUTOFF).season_usage
    assert usage.targets.value is usage.target_share.value is usage.avg_game_snap_share.value is None


def test_inconsistent_share_or_snap_units_are_unavailable() -> None:
    usage = player_usage([
        PlayerUsageGame(game(1), "A", targets=10, team_targets=5, offense_pct=80),
    ], CUTOFF).season_usage
    assert usage.targets.value == 10
    assert usage.target_share.reason == usage.avg_game_snap_share.reason == "missing_data"


def test_allowed_averages_position_totals_over_observed_defense_games() -> None:
    allowed = position_allowed([
        TeamAllowedGame(game(1), 1, rb_carries=20, rb_rec_yards=0),
        TeamAllowedGame(game(2), 1, rb_carries=10),
        TeamAllowedGame(game(3), 1),
    ], [1, 2], CUTOFF)
    carries = allowed[1]["rb_carries"]
    assert (carries.value, carries.observed_games, carries.eligible_games) == (15, 2, 3)
    assert (carries.window_start, carries.window_end) == (date(2026, 9, 1), date(2026, 9, 2))
    assert (carries.rank, carries.ranked_teams) == (1, 1)
    assert allowed[1]["rb_rec_yards"].value == 0
    assert allowed[1]["wr_rec_yards"].reason == "missing_data"
    assert allowed[2]["rb_carries"].reason == "no_history"


def test_competition_ranks_follow_one_decimal_display_ties_and_covered_teams() -> None:
    allowed = position_allowed([
        TeamAllowedGame(game(1), team, wr_rec_yards=value)
        for team, value in [(1, 80.04), (2, 80.01), (3, 100), (4, 60), (5, None)]
    ], range(1, 7), CUTOFF)
    assert [allowed[team]["wr_rec_yards"].rank for team in range(1, 7)] == [2, 2, 4, 1, None, None]
    assert all(allowed[team]["wr_rec_yards"].ranked_teams == 4 for team in allowed)
    assert allowed[1]["wr_rec_yards"].value == allowed[2]["wr_rec_yards"].value == 80


def test_negative_yards_are_real_but_nonfinite_allowed_values_are_missing() -> None:
    allowed = position_allowed([
        TeamAllowedGame(game(1), 1, rb_rush_yards=-2, wr_rec_yards=float("nan")),
    ], [1], CUTOFF)[1]
    assert allowed["rb_rush_yards"].value == -2
    assert allowed["wr_rec_yards"].reason == "missing_data"


@pytest.mark.parametrize("cutoff,reason", [
    (replace(CUTOFF, week=1), "no_history"),
    (replace(CUTOFF, kickoff=None), "unknown_kickoff"),
])
def test_opening_week_and_unknown_kickoff_have_structured_unavailable(cutoff: ContextCutoff, reason: str) -> None:
    usage = player_usage([PlayerUsageGame(game(1), "A", targets=10)], cutoff)
    assert usage.season_usage.targets.reason == usage.recent_usage.targets.reason == reason
    allowed = position_allowed([TeamAllowedGame(game(1), 1, rb_carries=10)], [1], cutoff)
    assert all(metric.reason == reason and metric.eligible_games == 0 for metric in allowed[1].values())


def test_duplicate_games_fail_instead_of_inflating_samples() -> None:
    row = PlayerUsageGame(game(1), "A")
    with pytest.raises(ValueError, match="one row per played game"):
        player_usage([row, row], CUTOFF)
    defense = TeamAllowedGame(game(1), 1)
    with pytest.raises(ValueError, match="one row per defense game"):
        position_allowed([defense, defense], [1], CUTOFF)


def test_context_contract_serializes_nested_metrics_and_teams_in_camel_case() -> None:
    allowed = position_allowed([], [1, 2], CUTOFF)
    matchup = NflMatchupContextSchema(
        away=NflMatchupTeamSchema(team_id=1, team="A", allowed=NflPositionAllowedSchema(**allowed[1])),
        home=NflMatchupTeamSchema(team_id=2, team="B", allowed=NflPositionAllowedSchema(**allowed[2])),
    )
    usage = player_usage([PlayerUsageGame(game(1), "OLD", targets=0)], CUTOFF)
    response = NflGameContextResponse(
        game_id=100, season=2026, week=7, cutoff_week=6, matchup_context=matchup,
        players=[NflContextPlayerSchema(
            player_id=10, name="Player", position="WR", team="A",
            season_usage=NflUsageWindowSchema.model_validate(usage.season_usage),
            recent_usage=NflUsageWindowSchema.model_validate(usage.recent_usage),
        )],
    ).model_dump(mode="json", by_alias=True)
    assert response["cutoffWeek"] == 6
    metric = response["players"][0]["seasonUsage"]["targets"]
    assert metric == {"value": 0, "observedGames": 1, "eligibleGames": 1,
                      "windowStart": "2026-09-01", "windowEnd": "2026-09-01", "reason": None}
    assert response["players"][0]["seasonUsage"]["teams"] == ["OLD"]
    assert response["matchupContext"]["away"]["allowed"]["rbCarries"]["rankedTeams"] == 0
    assert set(allowed[1]) == set(ALLOWED_MEASURES)
