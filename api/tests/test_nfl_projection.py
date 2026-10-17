from datetime import UTC, datetime, timedelta

from app.core.nfl_baseline import FULL_SEASON_GAMES
import pytest

from app.core.nfl_over_probability import OverProbability
from app.core.nfl_projection import (
    NFL_PROJECTION_MODEL_VERSION,
    NflHistoricalAverages, NflSeasonTouchdowns, anytime_td_probability, baseline_projection, edge, edge_is_comparable, line_quality_flags,
    model_projection, model_quality_flags, moneyline_is_stale, NflProjectionInput, NflUsageInput, opponent_adjustment_pct,
    quality_flags, slate_line_rank, usage_adjustment_pct,
)
from app.core.nfl_season_blend import apply_season_blend
from app.core.nfl_snap_share import NflSnapSeason, production_anytime_td_probability, season_snap_share
from app.nfl.markets import NflPropMarket
from app.routers.nfl import _projection_value
from app.services.nfl.slate import (
    _game_model, _history_sample, _slate_line, _weather_schema, slate_over_probability,
)


def _averages(games: int = 8) -> NflHistoricalAverages:
    return NflHistoricalAverages(games, 250, 33, 22, 18, 4, 65, 5, 0.5, 18.3)


def test_anytime_td_without_history_is_the_position_rate() -> None:
    assert anytime_td_probability([], 2026, 0.3) == (pytest.approx(1 - 2.718281828 ** -0.3, abs=0.005), 0.0)


def test_anytime_td_hot_streak_is_pulled_toward_the_position_rate() -> None:
    # Waller 2025: 6 TD in 9 games; 2026 week 1: none.
    probability, weighted_games = anytime_td_probability(
        [NflSeasonTouchdowns(2025, 9, 6 / 9), NflSeasonTouchdowns(2026, 1, 0.0)], 2026, 0.2,
    )

    assert weighted_games == pytest.approx(6.4)
    assert 0.25 < probability < 0.35


def test_anytime_td_counts_current_season_games_at_full_weight() -> None:
    # Hubbard: 11 TD in 2024, 4 in 2025, 2 in 2026 week 1.
    seasons = [NflSeasonTouchdowns(2024, 15, 11 / 15), NflSeasonTouchdowns(2025, 15, 4 / 15)]
    without_current, _ = anytime_td_probability(seasons, 2026, 0.3)
    with_current, weighted_games = anytime_td_probability(seasons + [NflSeasonTouchdowns(2026, 1, 2.0)], 2026, 0.3)

    assert weighted_games == pytest.approx(15.25)
    assert with_current > without_current


def test_anytime_td_ignores_seasons_too_old_or_after_the_line() -> None:
    too_old = anytime_td_probability([NflSeasonTouchdowns(2023, 17, 1.0)], 2026, 0.3)
    future = anytime_td_probability([NflSeasonTouchdowns(2027, 17, 1.0)], 2026, 0.3)

    assert too_old == future == anytime_td_probability([], 2026, 0.3)


def test_baseline_projection_uses_historical_average_for_stat_market() -> None:
    assert baseline_projection(NflPropMarket.PASSING_YARDS, _averages()) == 250
    assert baseline_projection(NflPropMarket.RECEPTIONS, _averages()) == 5


def test_anytime_touchdown_is_a_probability_not_a_touchdown_count() -> None:
    probability = baseline_projection(NflPropMarket.ANYTIME_TOUCHDOWN, _averages())
    assert 0 < probability < 1


def test_quality_flags_surface_small_sample_and_missing_live_lines() -> None:
    assert quality_flags(_averages(3)) == ["historical_baseline", "live_line_unavailable", "small_sample"]


@pytest.mark.parametrize(
    "games, segment, odds_type, expected",
    [
        (4, "full_game", "standard", True),
        (17, "full_game", "standard", True),
        # One game with no catches must not rank as a -6.5 under.
        (3, "full_game", "standard", False),
        (1, "full_game", "standard", False),
        (0, "full_game", "standard", False),
        (17, "first_half", "standard", False),
        (17, "full_game", "goblin", False),
        (17, "full_game", "demon", False),
        (17, "full_game", None, False),
    ],
)
def test_edge_is_comparable(games: int, segment: str, odds_type: str | None, expected: bool) -> None:
    assert edge_is_comparable(NflPropMarket.RECEIVING_YARDS, games, segment, odds_type) is expected


def test_anytime_td_gets_no_edge_until_the_book_comparison_is_adopted() -> None:
    assert not edge_is_comparable(NflPropMarket.ANYTIME_TOUCHDOWN, 34, "full_game", "standard")


def test_slate_anytime_td_line_keeps_its_probability_but_has_no_edge() -> None:
    result = _slate_line(_td_row(TD_SEASONS, "RB") | {"line": 0.5, "odds_type": "standard"}, 2026, None)

    assert result.projection is not None
    assert result.edge is None


def test_edge_is_positive_when_the_baseline_beats_the_line() -> None:
    assert edge(65.0, 58.5) == 6.5


def test_edge_is_negative_when_the_baseline_trails_the_line() -> None:
    assert edge(58.5, 65.0) == -6.5


def test_agreeing_with_the_market_is_zero_edge() -> None:
    assert edge(58.5, 58.5) == 0.0


def test_a_missing_side_is_none_not_zero() -> None:
    # Zero would read as "we agree with the market", which is a different claim
    # from "there is nothing to compare".
    assert edge(None, 58.5) is None
    assert edge(65.0, None) is None
    assert edge(None, None) is None


def test_a_baseline_from_another_season_is_flagged() -> None:
    flags = line_quality_flags(_averages(), baseline_season=2024, line_season=2026)
    assert "stale_baseline_season" in flags


def test_a_same_season_baseline_is_not_flagged_stale() -> None:
    flags = line_quality_flags(_averages(), baseline_season=2026, line_season=2026)
    assert "stale_baseline_season" not in flags


def test_a_baseline_from_the_lines_own_unfinished_season_is_flagged_partial() -> None:
    flags = line_quality_flags(_averages(6), baseline_season=2026, line_season=2026)

    assert "partial_season_baseline" in flags
    assert "stale_baseline_season" not in flags


def test_a_completed_season_baseline_carries_neither_season_flag() -> None:
    flags = line_quality_flags(
        _averages(FULL_SEASON_GAMES), baseline_season=2026, line_season=2026
    )

    assert "partial_season_baseline" not in flags
    assert "stale_baseline_season" not in flags


def test_a_fallback_baseline_is_stale_but_not_partial() -> None:
    # 2025 is finished. The problem with it is that it is the wrong season, not
    # that it is unfinished, so only one flag should fire.
    flags = line_quality_flags(_averages(16), baseline_season=2025, line_season=2026)

    assert "stale_baseline_season" in flags
    assert "partial_season_baseline" not in flags


def test_partial_and_small_sample_are_independent_signals() -> None:
    # 12 games is plenty to bet on and still not a finished season; 2 games is
    # thin regardless of which season it came from.
    plenty = line_quality_flags(_averages(12), baseline_season=2026, line_season=2026)
    thin = line_quality_flags(_averages(2), baseline_season=2026, line_season=2026)

    assert "partial_season_baseline" in plenty and "small_sample" not in plenty
    assert "partial_season_baseline" in thin and "small_sample" in thin


def test_an_unknown_season_carries_no_partial_flag() -> None:
    assert "partial_season_baseline" not in line_quality_flags(_averages(3), None, 2026)


def test_an_unknown_season_on_either_side_is_not_flagged_stale() -> None:
    assert "stale_baseline_season" not in line_quality_flags(_averages(), 2024, None)
    assert "stale_baseline_season" not in line_quality_flags(_averages(), None, 2026)


def test_a_non_full_game_segment_is_flagged_as_not_comparable() -> None:
    # Whole-game averages cannot be priced against a first-quarter line.
    assert "segment_mismatch" in line_quality_flags(_averages(), segment="q1")
    assert "segment_mismatch" in line_quality_flags(_averages(), segment="season")
    assert "segment_mismatch" not in line_quality_flags(_averages(), segment="full_game")


def test_alternate_lines_are_flagged_as_not_the_market_price() -> None:
    # Goblin and demon lines are moved off the market on purpose, so the gap to a
    # projection measures the payout ladder rather than a mispricing.
    assert "non_standard_line" in line_quality_flags(_averages(), odds_type="demon")
    assert "non_standard_line" in line_quality_flags(_averages(), odds_type="goblin")
    assert "non_standard_line" not in line_quality_flags(_averages(), odds_type="standard")


def test_an_unknown_odds_type_is_not_flagged() -> None:
    # Rows predating the column are backfilled; absence is not evidence of alternate.
    assert "non_standard_line" not in line_quality_flags(_averages(), odds_type=None)


def test_line_quality_flags_still_report_small_sample() -> None:
    assert "small_sample" in line_quality_flags(_averages(2))
    assert "small_sample" not in line_quality_flags(_averages(8))


def test_model_regresses_small_samples_to_position_average() -> None:
    assert model_projection(NflProjectionInput(100, 60, 2)) == 80


def test_model_uses_recent_average_for_adequate_sample() -> None:
    assert model_projection(NflProjectionInput(100, 60, 4)) == 100


def test_model_market_adjustment_orients_home_and_away() -> None:
    home = model_projection(NflProjectionInput(100, 60, 4, 0.60, True))
    away = model_projection(NflProjectionInput(100, 60, 4, 0.60, False))
    assert home == 108
    assert away == 92


def test_missing_or_stale_market_does_not_adjust_projection() -> None:
    assert model_projection(NflProjectionInput(100, 60, 4)) == 100
    assert model_projection(NflProjectionInput(100, 60, 4, 0.60, True, True)) == 100
    assert model_quality_flags(NflProjectionInput(100, 60, 2)) == [
        "recent_market_model", "small_sample", "market_missing", "opponent_data_missing",
    ]


@pytest.mark.parametrize(
    "opponent_average, league_average, opponent_games, expected",
    [
        (130, 100, 12, 10.0),
        (70, 100, 12, -10.0),
        (100, 100, 12, 0.0),
        (200, 100, 12, 10.0),
        (70, 100, 3, None),
        (None, 100, 12, None),
        (100, 0, 12, None),
    ],
)
def test_opponent_adjustment_is_bounded_and_requires_valid_evidence(
    opponent_average: float | None,
    league_average: float,
    opponent_games: int,
    expected: float | None,
) -> None:
    input = NflProjectionInput(
        100, 60, 4,
        opponent_average=opponent_average,
        league_position_average=league_average,
        opponent_games=opponent_games,
    )

    assert opponent_adjustment_pct(input) == expected


def test_opponent_adjustment_changes_projection_only_when_safe() -> None:
    favorable = NflProjectionInput(100, 60, 4, opponent_average=130, league_position_average=100, opponent_games=12)
    unfavorable = NflProjectionInput(100, 60, 4, opponent_average=70, league_position_average=100, opponent_games=12)
    small_sample = NflProjectionInput(100, 60, 4, opponent_average=130, league_position_average=100, opponent_games=3)

    assert model_projection(favorable) == 110
    assert model_projection(unfavorable) == 90
    assert model_projection(small_sample) == 100
    assert model_quality_flags(favorable)[-1] == "opponent_adjusted"
    assert model_quality_flags(small_sample)[-1] == "opponent_small_sample"


def test_slate_line_surfaces_position_matched_opponent_adjustment() -> None:
    row = {
        "id": 1, "game_id": 2, "player_id": 3, "player_name": "Receiver", "position": "WR",
        "player_team_id": 4, "home_team_id": 4, "market": "receiving_yards", "segment": "full_game",
        "opponent_team": "BUF",
        "odds_type": "standard", "line": 99.5, "provider": "prizepicks", "fetched_at": datetime.now(UTC),
        "baseline_season": 2026, "baseline_reason": "current_season",
        "averages": _average_dict(4, 100), "position_averages": _average_dict(20, 60),
        "opponent_averages": _average_dict(12, 130), "league_position_averages": _average_dict(100, 100),
    }

    result = _slate_line(row, 2026, 0.60)

    assert result.projection == 118.8
    assert result.opponent_adjustment_pct == 10
    assert result.opponent_sample_games == 12
    assert result.opponent_team == "BUF"
    assert result.opponent_position_average == 130
    assert "opponent_adjusted" in result.quality_flags


def _receiver_row() -> dict:
    return {
        "id": 1, "game_id": 2, "player_id": 3, "player_name": "Receiver", "position": "WR",
        "player_team_id": 4, "home_team_id": 4, "market": "receiving_yards", "segment": "full_game",
        "opponent_team": "BUF",
        "odds_type": "standard", "line": 99.5, "provider": "prizepicks", "fetched_at": datetime.now(UTC),
        "baseline_season": 2026, "baseline_reason": "current_season",
        "averages": _average_dict(4, 100), "position_averages": _average_dict(20, 60),
        "opponent_averages": _average_dict(12, 130), "league_position_averages": _average_dict(100, 100),
    }


def test_slate_line_skips_a_stale_moneyline_and_says_so() -> None:
    result = _slate_line(_receiver_row(), 2026, 0.60, market_is_stale=True)

    # Opponent adjustment only: 100 x 1.10, without the favorite's +8%.
    assert result.projection == 110
    assert "market_stale" in result.quality_flags


KICKOFF = datetime(2026, 9, 27, 17, 0, tzinfo=UTC)


def test_a_moneyline_fetched_nine_days_before_kickoff_is_stale() -> None:
    assert moneyline_is_stale(datetime(2026, 9, 18, 17, 0, tzinfo=UTC), KICKOFF, KICKOFF - timedelta(hours=1))


def test_a_moneyline_fetched_two_days_before_kickoff_is_fresh() -> None:
    fetched = datetime(2026, 9, 25, 17, 0, tzinfo=UTC)

    assert not moneyline_is_stale(fetched, KICKOFF, KICKOFF - timedelta(hours=1))
    # Revisited two weeks later, the age is still measured at kickoff.
    assert not moneyline_is_stale(fetched, KICKOFF, KICKOFF + timedelta(days=14))


def test_a_missing_moneyline_is_not_called_stale() -> None:
    assert not moneyline_is_stale(None, KICKOFF, KICKOFF)


def test_anytime_td_history_marks_each_game_scored_or_not() -> None:
    rows = [_history_row(2, 10) | {"touchdowns": touchdowns} for touchdowns in (2, 0, 1, 0, 0)]

    sample = _history_sample(NflPropMarket.ANYTIME_TOUCHDOWN, rows, limit=5)

    assert [item.value for item in sample.values] == [1.0, 0.0, 1.0, 0.0, 0.0]
    assert sample.average == 0.4


def test_history_sample_uses_the_prop_market_and_preserves_newest_first_order() -> None:
    rows = [
        _history_row(opponent_team_id=2, opponent_team="CAR", receiving_yards=61),
        _history_row(opponent_team_id=3, opponent_team="ATL", receiving_yards=42),
        _history_row(opponent_team_id=2, receiving_yards=25),
    ]

    sample = _history_sample(NflPropMarket.RECEIVING_YARDS, rows, limit=2)

    assert sample.average == 51.5
    assert [(item.value, item.opponent_team) for item in sample.values] == [(61, "CAR"), (42, "ATL")]


def test_slate_line_keeps_recent_and_scheduled_opponent_history_separate() -> None:
    row = _usage_row("receiving_yards") | {"opponent_team_id": 2}
    history = [
        _history_row(opponent_team_id=2, receiving_yards=61),
        _history_row(opponent_team_id=3, receiving_yards=42),
        _history_row(opponent_team_id=2, receiving_yards=25),
    ]

    result = _slate_line(row, 2026, None, history)

    assert [item.value for item in result.recent_form.values] == [61, 42, 25]
    assert [item.value for item in result.opponent_history.values] == [61, 25]
    assert result.opponent_history.average == 43


def test_weather_schema_uses_registry_venue_when_no_snapshot_exists() -> None:
    assert _weather_schema({"home_team": "LAC"}, {"venue_type": None}).venue_type == "dome"


def test_stale_baseline_edges_rank_below_current_season_edges() -> None:
    current_small = slate_line_rank(2.0, ["historical_baseline"])
    stale_large = slate_line_rank(24.8, ["historical_baseline", "stale_baseline_season"])
    unpriced = slate_line_rank(None, ["historical_baseline"])

    assert current_small < stale_large < unpriced


def test_slate_rank_keeps_the_largest_absolute_edge_first_within_a_tier() -> None:
    ordered = sorted(
        [(-3.0, False), (12.0, False), (24.8, True), (-30.0, True), (7.0, False)],
        key=lambda item: slate_line_rank(item[0], ["stale_baseline_season"] if item[1] else []),
    )

    assert [value for value, _ in ordered] == [12.0, 7.0, -3.0, -30.0, 24.8]


def _usage(games: int = 12, targets: float = 10, target_share: float = 0.40, position_targets: float = 6) -> NflUsageInput:
    return NflUsageInput(games, targets, target_share, position_targets, 0.24)


@pytest.mark.parametrize(
    "usage, expected, flag",
    [
        (_usage(targets=12, target_share=0.48), 7.0, "usage_adjusted"),
        (_usage(targets=8, target_share=0.32), -7.0, "usage_adjusted"),
        (_usage(), 0.0, "usage_adjusted"),
        (_usage(targets=15, target_share=0.60), 8.0, "usage_adjusted"),
        (_usage(games=6, targets=12, target_share=0.48), 3.5, "usage_adjusted"),
        (_usage(games=3, targets=15, target_share=0.60), None, "usage_small_sample"),
        (_usage(position_targets=0), None, "usage_data_invalid"),
        (None, None, "usage_data_missing"),
    ],
)
def test_usage_adjustment_is_shrunk_bounded_and_requires_valid_evidence(
    usage: NflUsageInput | None,
    expected: float | None,
    flag: str,
) -> None:
    input = NflProjectionInput(100, 60, 4, usage_applicable=True, usage=usage)

    assert usage_adjustment_pct(input) == expected
    assert model_quality_flags(input)[-1] == flag


def test_usage_adjustment_changes_projection_only_when_safe() -> None:
    favorable = NflProjectionInput(100, 60, 4, usage_applicable=True, usage=_usage(targets=12, target_share=0.48))
    thin = NflProjectionInput(100, 60, 4, usage_applicable=True, usage=_usage(games=3, targets=15, target_share=0.60))

    assert model_projection(favorable) == 107
    assert model_projection(thin) == 100


def test_usage_is_ignored_for_markets_it_does_not_apply_to() -> None:
    input = NflProjectionInput(100, 60, 4, usage=_usage(targets=15, target_share=0.60))

    assert usage_adjustment_pct(input) is None
    assert model_projection(input) == 100
    assert not any(flag.startswith("usage_") for flag in model_quality_flags(input))


def _usage_row(market: str) -> dict:
    return {
        "id": 1, "game_id": 2, "player_id": 3, "player_name": "Receiver", "position": "WR",
        "player_team_id": 4, "home_team_id": 4, "market": market, "segment": "full_game",
        "odds_type": "standard", "line": 99.5, "provider": "prizepicks", "fetched_at": datetime.now(UTC),
        "baseline_season": 2026, "baseline_reason": "current_season",
        "averages": _average_dict(4, 100), "position_averages": _average_dict(20, 60),
        "opponent_averages": None, "league_position_averages": None,
        "usage": {"games": 12, "targets": 12, "target_share": 0.48},
        "position_usage": {"games": 400, "targets": 6, "target_share": 0.24},
    }


def test_slate_line_flags_a_player_whose_team_is_not_in_the_game() -> None:
    in_game = _slate_line(_usage_row("receiving_yards") | {"opponent_team": "BUF", "opponent_team_id": 2}, 2026, None)
    elsewhere = _slate_line(_usage_row("receiving_yards") | {"opponent_team": None, "opponent_team_id": None}, 2026, None)
    no_team = _slate_line(
        _usage_row("receiving_yards") | {"player_team_id": None, "opponent_team": None, "opponent_team_id": None},
        2026, None,
    )

    assert "team_not_in_game" not in in_game.quality_flags
    assert "team_not_in_game" in elsewhere.quality_flags
    assert "team_not_in_game" in no_team.quality_flags


def test_slate_line_surfaces_injury_and_depth_without_touching_the_projection() -> None:
    base = _usage_row("receiving_yards") | {"opponent_team": "BUF", "opponent_team_id": 2}
    plain = _slate_line(base, 2026, None)
    result = _slate_line(base | {
        "injury_status": "Questionable", "practice_status": "Limited Participation in Practice",
        "injury": "Hamstring", "depth_team_id": 4, "depth_position": "WR", "depth_rank": 1,
        "previous_depth_team_id": 4, "previous_depth_position": "WR", "previous_depth_rank": 2,
    }, 2026, None)

    assert (result.injury_status, result.practice_status, result.injury) == (
        "Questionable", "Limited Participation in Practice", "Hamstring",
    )
    assert (result.depth_position, result.depth_rank, result.previous_depth_rank) == ("WR", 1, 2)
    assert result.quality_flags[-2:] == ["injury_questionable", "depth_promoted"]
    assert (result.projection, result.edge) == (plain.projection, plain.edge)


def test_slate_line_without_availability_data_has_null_fields_and_no_flags() -> None:
    result = _slate_line(_usage_row("receiving_yards") | {"opponent_team": "BUF", "opponent_team_id": 2}, 2026, None)

    assert (result.injury_status, result.depth_rank, result.previous_depth_rank) == (None, None, None)
    assert not {"injury_out", "injury_questionable", "depth_new", "depth_promoted"} & set(result.quality_flags)


def test_slate_line_surfaces_receiving_usage_adjustment() -> None:
    result = _slate_line(_usage_row("receiving_yards"), 2026, None)

    assert result.projection == 107
    assert result.usage_adjustment_pct == 7
    assert result.usage_sample_games == 12
    assert "usage_adjusted" in result.quality_flags


def test_slate_line_reports_missing_usage_explicitly() -> None:
    row = _usage_row("receiving_yards") | {"usage": None}

    result = _slate_line(row, 2026, None)

    assert result.projection == 100
    assert (result.usage_adjustment_pct, result.usage_sample_games) == (None, None)
    assert "usage_data_missing" in result.quality_flags


def test_slate_line_leaves_non_receiving_markets_without_usage_fields() -> None:
    result = _slate_line(_usage_row("rushing_yards"), 2026, None)

    assert (result.usage_adjustment_pct, result.usage_sample_games) == (None, None)
    assert not any(flag.startswith("usage_") for flag in result.quality_flags)


def _td_row(td_seasons: list[dict[str, float | int]], position: str = "WR") -> dict:
    # The selected season (2025) alone would say 6 TD in 9 games, about 49%.
    # WR by default: its anytime-TD baseline is untouched by the RB/TE snap-share blend.
    selected = _average_dict(9, 30) | {"touchdowns": 6 / 9}
    return _usage_row("anytime_touchdown") | {
        "position": position, "line": 0.5, "baseline_season": 2025, "baseline_reason": "previous_season",
        "averages": selected, "position_averages": _average_dict(400, 30) | {"touchdowns": 0.2},
        "usage": None, "position_usage": None, "td_seasons": td_seasons,
    }


def test_slate_line_blends_seasons_for_anytime_td() -> None:
    result = _slate_line(_td_row([
        {"season": 2025, "games": 9, "touchdowns": 6 / 9}, {"season": 2026, "games": 1, "touchdowns": 0.0},
    ]), 2026, None)

    assert result.projection == anytime_td_probability(
        [NflSeasonTouchdowns(2025, 9, 6 / 9), NflSeasonTouchdowns(2026, 1, 0.0)], 2026, 0.2,
    )[0]
    assert result.projection < 0.35
    assert (result.baseline_season, result.baseline_reason, result.games_in_sample) == (2026, "blended_seasons", 10)
    assert "stale_baseline_season" not in result.quality_flags
    assert "partial_season_baseline" in result.quality_flags
    assert result.edge is None


def test_anytime_td_labels_ignore_seasons_outside_the_weights() -> None:
    result = _slate_line(_td_row([
        {"season": 2022, "games": 17, "touchdowns": 1.0}, {"season": 2025, "games": 9, "touchdowns": 6 / 9},
    ]), 2026, None)

    assert (result.baseline_season, result.games_in_sample) == (2025, 9)
    assert "stale_baseline_season" in result.quality_flags


def test_projections_endpoint_value_blends_anytime_td_and_keeps_flat_averages_elsewhere() -> None:
    row = {
        "td_seasons": [{"season": 2025, "games": 9, "touchdowns": 6 / 9}, {"season": 2026, "games": 1, "touchdowns": 0.0}],
        "position_td_rate": 0.2,
    }
    averages = NflHistoricalAverages(10, 0, 0, 0, 0, 0, 30, 3, 0.6, None)

    assert _projection_value(NflPropMarket.ANYTIME_TOUCHDOWN, row, 2026, averages) == anytime_td_probability(
        [NflSeasonTouchdowns(2025, 9, 6 / 9), NflSeasonTouchdowns(2026, 1, 0.0)], 2026, 0.2,
    )[0]
    assert _projection_value(NflPropMarket.RECEIVING_YARDS, row, 2026, averages) == 30


TD_SEASONS = [{"season": 2025, "games": 9, "touchdowns": 6 / 9}, {"season": 2026, "games": 1, "touchdowns": 0.0}]
SNAP_SEASONS = [{"season": 2025, "games": 12, "share": 0.85}, {"season": 2026, "games": 1, "share": 0.9}]


def test_rb_and_te_anytime_td_blend_the_frozen_snap_share_model() -> None:
    for position in ("RB", "TE"):
        row = _td_row(TD_SEASONS, position) | {"snap_seasons": SNAP_SEASONS, "position_snap_share": 0.45}

        result = _slate_line(row, 2026, None)

        expected, _ = production_anytime_td_probability(
            position, [NflSeasonTouchdowns(2025, 9, 6 / 9), NflSeasonTouchdowns(2026, 1, 0.0)],
            [NflSnapSeason(2025, 12, 0.85), NflSnapSeason(2026, 1, 0.9)], 2026, 0.2, 0.45,
        )
        assert result.projection == expected
        assert result.projection != _slate_line(_td_row(TD_SEASONS, "WR"), 2026, None).projection
        assert result.snap_share_games == 13
        assert result.snap_share == pytest.approx(
            season_snap_share([NflSnapSeason(2025, 12, 0.85), NflSnapSeason(2026, 1, 0.9)], 2026, 0.45)[0], abs=1e-3,
        )
        assert "snap_share_unavailable" not in result.quality_flags
        assert result.projection_model_version == "opponent-dvp-tg-blend-usage-snap-v4"


def test_qb_and_wr_anytime_td_ignore_snap_share() -> None:
    for position in ("QB", "WR"):
        plain = _slate_line(_td_row(TD_SEASONS, position), 2026, None)
        with_snaps = _slate_line(
            _td_row(TD_SEASONS, position) | {"snap_seasons": SNAP_SEASONS, "position_snap_share": 0.45}, 2026, None,
        )

        assert with_snaps.projection == plain.projection == anytime_td_probability(
            [NflSeasonTouchdowns(2025, 9, 6 / 9), NflSeasonTouchdowns(2026, 1, 0.0)], 2026, 0.2,
        )[0]
        assert (with_snaps.snap_share, with_snaps.snap_share_games) == (None, None)
        assert "snap_share_unavailable" not in with_snaps.quality_flags


def test_an_rb_without_snap_history_is_flagged_and_uses_the_position_share() -> None:
    row = _td_row(TD_SEASONS, "RB") | {"snap_seasons": [], "position_snap_share": 0.45}

    result = _slate_line(row, 2026, None)

    assert (result.snap_share, result.snap_share_games) == (None, 0)
    assert "snap_share_unavailable" in result.quality_flags
    assert result.projection == production_anytime_td_probability(
        "RB", [NflSeasonTouchdowns(2025, 9, 6 / 9), NflSeasonTouchdowns(2026, 1, 0.0)], [], 2026, 0.2, 0.45,
    )[0]


def test_rb_non_td_markets_carry_no_snap_fields() -> None:
    row = _usage_row("rushing_yards") | {"position": "RB", "snap_seasons": SNAP_SEASONS, "position_snap_share": 0.45}

    result = _slate_line(row, 2026, None)

    assert (result.snap_share, result.snap_share_games) == (None, None)
    assert "snap_share_unavailable" not in result.quality_flags


def test_projections_and_slate_agree_on_an_rb_anytime_td_probability() -> None:
    slate_row = _td_row(TD_SEASONS, "RB") | {"snap_seasons": SNAP_SEASONS, "position_snap_share": 0.45}
    # /projections carries the position TD rate directly; the slate reads it from position averages.
    projections_row = {
        "position": "RB", "td_seasons": TD_SEASONS, "position_td_rate": 0.2,
        "snap_seasons": SNAP_SEASONS, "position_snap_share": 0.45,
    }
    averages = NflHistoricalAverages(10, 0, 0, 0, 0, 0, 30, 3, 0.6, None)

    assert _projection_value(NflPropMarket.ANYTIME_TOUCHDOWN, projections_row, 2026, averages) == _slate_line(
        slate_row, 2026, None,
    ).projection


def test_slate_line_keeps_single_season_baseline_for_other_markets() -> None:
    row = _usage_row("rushing_yards") | {"td_seasons": [{"season": 2024, "games": 17, "touchdowns": 1.0}]}
    plain = _slate_line(_usage_row("rushing_yards"), 2026, None)
    result = _slate_line(row, 2026, None)

    assert result.projection == plain.projection
    assert (result.baseline_season, result.baseline_reason, result.games_in_sample) == (2026, "current_season", 4)


def _average_dict(games: int, receiving_yards: float) -> dict[str, float | int | None]:
    return {
        "games": games, "passing_yards": 0, "passing_attempts": 0, "passing_completions": 0,
        "rushing_yards": 0, "rushing_attempts": 0, "receiving_yards": receiving_yards,
        "receptions": 0, "touchdowns": 0, "fantasy_points": None,
    }


def _history_row(
    opponent_team_id: int, receiving_yards: float, opponent_team: str | None = None,
) -> dict[str, float | int | str | None]:
    return {
        "opponent_team_id": opponent_team_id,
        "opponent_team": opponent_team,
        "passing_yards": 0, "passing_attempts": 0, "passing_completions": 0,
        "rushing_yards": 0, "rushing_attempts": 0, "receiving_yards": receiving_yards,
        "receptions": 0, "touchdowns": 0, "fantasy_points": None,
    }


def test_game_model_uses_the_displayed_books_moneylines_and_the_replayed_total() -> None:
    model = _game_model(
        ("2026_03_PHI_CHI", 1540.0, 1500.0), {"2026_03_PHI_CHI": 44.25},
        {"book": "draftkings", "home_moneyline": -150, "away_moneyline": 130, "home_spread": -3.0, "total": 44.5},
    )

    assert model is not None
    assert model.model_version == "nfl-elo-v1"
    assert model.home_spread == pytest.approx(-(40 + 48) / 25)
    assert model.total == 44.25
    assert model.market_home_win_probability == pytest.approx(0.5798, abs=1e-4)
    assert model.model_dump(by_alias=True)["homeSpread"] == model.home_spread


def test_game_model_without_odds_keeps_the_model_and_leaves_the_market_empty() -> None:
    model = _game_model(("2026_04_KC_NYG", 1500.0, 1600.0), {"2026_04_KC_NYG": 41.0}, None)

    assert model is not None
    assert model.market_home_win_probability is None
    assert model.home_win_probability < 0.5


def test_game_model_is_empty_without_pre_game_ratings() -> None:
    assert _game_model(None, {}, {"home_moneyline": -150, "away_moneyline": 130}) is None


def _passing_season(games: int, yards: float) -> dict:
    averages = _average_dict(games, 0) | {"passing_yards": yards}
    return {
        "averages": averages, "position_averages": _average_dict(games * 30, 0) | {"passing_yards": 200},
        "usage": None, "position_usage": None,
    }


def _two_season_line(market: str, current_games: int) -> dict:
    """2026 line with `current_games` at 300 yards and a full 2025 at 200; fields as the chooser sets them."""
    seasons = {2026: _passing_season(current_games, 300), 2025: _passing_season(17, 200)}
    chosen = 2026 if current_games >= 4 else 2025
    return _usage_row(market) | {
        "position": "QB", "usage": None, "position_usage": None,
        "baseline_season": chosen, "baseline_reason": "current_season" if chosen == 2026 else "previous_season",
        "averages": seasons[chosen]["averages"], "position_averages": seasons[chosen]["position_averages"],
        "baseline_seasons": seasons,
    }


def test_slate_blends_seasons_for_adopted_passing_markets_only() -> None:
    passing = _slate_line(apply_season_blend(_two_season_line("passing_yards", 5), 2026), 2026, None)
    rushing = _slate_line(apply_season_blend(_two_season_line("rushing_yards", 5), 2026), 2026, None)

    assert passing.projection == round((5 * 300 + 0.6 * 17 * 200) / (5 + 0.6 * 17), 2)
    assert (passing.games_in_sample, passing.baseline_reason, passing.baseline_season) == (22, "current_previous_blend", 2026)
    assert (rushing.games_in_sample, rushing.baseline_reason) == (5, "current_season")
    assert passing.projection_model_version == "opponent-dvp-tg-blend-usage-snap-v4"


def test_blended_line_keeps_the_season_flags_of_its_own_season() -> None:
    in_progress = _slate_line(apply_season_blend(_two_season_line("passing_yards", 5), 2026), 2026, None)
    early_blend = _slate_line(apply_season_blend(_two_season_line("passing_yards", 2), 2026), 2026, None)
    early_switch = _slate_line(apply_season_blend(_two_season_line("rushing_yards", 2), 2026), 2026, None)

    # 22 blended games, but only 5 of the 17 in 2026 are played.
    assert "partial_season_baseline" in in_progress.quality_flags
    assert "stale_baseline_season" not in in_progress.quality_flags
    # Two current games: the blend is mostly 2025, so it ranks as stale like the switch does.
    for line in (early_blend, early_switch):
        assert "stale_baseline_season" in line.quality_flags
        assert line.baseline_season == 2025
    assert early_blend.games_in_sample == 19
    assert "small_sample" not in early_blend.quality_flags


def test_anytime_td_ignores_the_season_blend() -> None:
    row = _td_row(TD_SEASONS) | {"baseline_seasons": {2026: _passing_season(5, 300), 2025: _passing_season(17, 200)}}

    assert apply_season_blend(row, 2026) is row


def _passing_row(market: str) -> dict:
    return _receiver_row() | {
        "position": "QB", "market": market,
        "averages": _average_dict(4, 0) | {market: 100},
        "position_averages": _average_dict(20, 0) | {market: 60},
        "opponent_averages": None, "league_position_averages": None,
    }


@pytest.mark.parametrize("market", ["passing_attempts", "passing_completions", "passing_yards"])
def test_passing_lines_take_no_moneyline_bump_and_carry_no_market_flag(market: str) -> None:
    favored = _slate_line(_passing_row(market), 2026, 0.75)
    stale = _slate_line(_passing_row(market), 2026, 0.75, market_is_stale=True)
    missing = _slate_line(_passing_row(market), 2026, None)

    assert favored.projection == stale.projection == missing.projection == 100
    for line in (favored, stale, missing):
        assert not {"market_missing", "market_stale"} & set(line.quality_flags)


def test_receiving_lines_keep_the_moneyline_bump_and_its_flags() -> None:
    favored = _slate_line(_receiver_row(), 2026, 0.75)
    missing = _slate_line(_receiver_row(), 2026, None)

    assert favored.projection == round(100 * 1.08 * 1.10, 2)
    assert "market_missing" in missing.quality_flags
    assert "market_stale" in _slate_line(_receiver_row(), 2026, 0.75, market_is_stale=True).quality_flags


FIT = {("receiving_yards", "WR"): tuple(0.5 + i * 0.025 for i in range(41))}


def _over(**changes: object) -> OverProbability | None:
    args: dict = {
        "market": "receiving_yards", "position": "WR", "segment": "full_game", "games": 4,
        "projection": 60.0, "line": 44.5,
    } | changes
    return slate_over_probability(**args, fit_version=NFL_PROJECTION_MODEL_VERSION, tables=FIT, shown={"receiving_yards"})


def test_over_probability_is_served_on_a_shown_market_whatever_the_odds_type() -> None:
    over = _over()

    assert over is not None and 0.5 < over.p_over < 1.0


@pytest.mark.parametrize("changes", [
    {"market": "anytime_touchdown"},
    {"market": "receptions"},
    {"segment": "first_half"},
    {"games": 3},
    {"position": "TE"},
    {"projection": None},
    {"line": 45.0},
])
def test_over_probability_is_withheld_outside_the_fit(changes: dict) -> None:
    assert _over(**changes) is None


def test_over_probability_is_withheld_when_the_fit_is_for_another_projection() -> None:
    stale = slate_over_probability(
        "receiving_yards", "WR", "full_game", 4, 60.0, 44.5,
        fit_version="an-older-model", tables=FIT, shown={"receiving_yards"},
    )

    assert stale is None


def test_slate_line_serves_over_probability_on_a_goblin_line() -> None:
    goblin = _slate_line(_receiver_row() | {"odds_type": "goblin", "line": 60.5}, 2026, None)
    receptions = _slate_line(_usage_row("receptions") | {"line": 4.5}, 2026, None)

    assert goblin.edge is None
    assert goblin.p_over is not None and goblin.p_under == pytest.approx(1 - goblin.p_over)
    assert goblin.over_probability_version == "nfl-pover-v1"
    assert receptions.p_over is None and receptions.over_probability_version is None
