"""The targets reference matches its fixed baseline and freezes with truthful evidence."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.core.nfl_availability import NflAvailability
from app.core.nfl_targets_projection import TargetsObservation, TargetsProjectionInput, project_targets
from app.repositories.nfl_targets import TargetsHistoryGame, TargetsServingLine
from app.services.nfl.prop_predictions import prediction_row
from app.services.nfl.targets import targets_over_probability, targets_slate_line

FETCHED = datetime(2026, 10, 24, 15, tzinfo=UTC)
NOW = datetime(2026, 10, 24, 16, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 25, 17, tzinfo=UTC)
QUANTILES = tuple(index / 20 for index in range(41))


def _game(game_id: int, value: float | None, *, season: int = 2026, week: int | None = None) -> TargetsHistoryGame:
    return TargetsHistoryGame(
        TargetsObservation(game_id, season, week if week is not None else game_id, None, value),
        opponent_team_id=3, opponent_team="BUF",
    )


DEFAULT_HISTORY = tuple(_game(index, value) for index, value in enumerate([1, 2, 4, 6], start=1))


def _source(history: tuple[TargetsHistoryGame, ...] = DEFAULT_HISTORY) -> TargetsServingLine:
    return TargetsServingLine(
        line_id=70, game_id=50, player_id=7, player_name="Receiver", position="WR", player_team_id=2,
        opponent_team_id=3, opponent_team="BUF", start_utc=KICKOFF,
        market="receiving_targets", segment="full_game", odds_type="standard", line=4.5,
        provider="prizepicks", fetched_at=FETCHED,
        input=TargetsProjectionInput(2026, 7, tuple(game.observation for game in history)), history=history,
        availability=NflAvailability(), practice_status=None, injury=None,
    )


@pytest.mark.parametrize(("values", "expected"), [
    ([], None), ([1, 2, 4], None), ([1, 2, 4, 6], 3.25),
    ([1, 2, 4, 6, 7, 8], 4.67), ([0, 0, 0, 0], 0.0),
])
def test_the_served_reference_is_exactly_the_fixed_projection(values: list[float], expected: float | None) -> None:
    source = _source(tuple(_game(index, value) for index, value in enumerate(values, start=1)))

    result = targets_slate_line(source)
    baseline = project_targets(source.input)

    assert result.projection == baseline.projection == expected
    assert result.games_in_sample == baseline.games_in_sample == len(values)
    assert (result.baseline_season, result.baseline_reason) == (baseline.baseline_season, baseline.baseline_reason)
    assert result.edge == (round(expected - 4.5, 2) if expected is not None else None)
    assert result.projection_model_version == "nfl-targets-v1"
    assert result.quality_flags == ["historical_baseline", *baseline.quality_flags]
    assert (result.p_over, result.p_under, result.over_probability_version) == (None, None, None)


def test_previous_season_baseline_counts_valid_observations_and_ignores_moneyline_inputs() -> None:
    history = tuple(replace(game, observation=replace(game.observation, season=2025)) for game in DEFAULT_HISTORY)
    history += (_game(5, 100, week=1), _game(6, 100, week=2))
    source = _source(history)
    source = replace(source, input=replace(source.input, home_market_prob=0.99, player_is_home=True))

    result = targets_slate_line(source)

    assert (result.projection, result.baseline_season, result.baseline_reason, result.games_in_sample) == (
        3.25, 2025, "previous_season", 4,
    )
    assert result.quality_flags == ["historical_baseline", "stale_baseline_season"]


def test_history_uses_valid_pre_week_targets_newest_first_and_separates_opponent_games() -> None:
    history = (
        _game(1, 0), _game(2, 2), replace(_game(3, 4), opponent_team_id=4, opponent_team="DET"),
        _game(4, 6), _game(5, 8), _game(6, 10), _game(7, 100),
        _game(8, float("nan"), week=3), _game(9, None, week=4), _game(10, -1, week=5),
        _game(11, float("inf"), week=6), _game(12, 100, season=2027, week=1),
    )

    result = targets_slate_line(_source(history))

    assert result.projection == 5.0 and result.games_in_sample == 6
    assert [item.value for item in result.recent_form.values] == [10, 8, 6, 4, 2]
    assert result.recent_form.average == 6.0
    assert [item.opponent_team for item in result.recent_form.values] == ["BUF", "BUF", "BUF", "DET", "BUF"]
    assert [item.value for item in result.opponent_history.values] == [10, 8, 6, 2, 0]
    assert result.opponent_history.average == 5.2
    assert result.opponent_allowed_history.average is None and result.opponent_allowed_history.values == []


def test_missing_team_keeps_the_baseline_but_no_opponent_evidence_and_flags_availability() -> None:
    source = replace(_source(), opponent_team_id=None, opponent_team=None, player_team_id=None,
                     availability=NflAvailability("Out", 2, "WR", 1, 2, "WR", 2),
                     practice_status="DNP", injury="Ankle")

    result = targets_slate_line(source)

    assert result.projection == 3.25 and result.opponent_team is None
    assert result.opponent_history.average is None and result.opponent_history.values == []
    assert result.quality_flags == ["historical_baseline", "injury_out", "depth_promoted", "team_not_in_game"]
    assert (result.injury_status, result.practice_status, result.injury) == ("Out", "DNP", "Ankle")
    assert (result.depth_position, result.depth_rank, result.previous_depth_position, result.previous_depth_rank) == (
        "WR", 1, "WR", 2,
    )


def test_v4_adjustments_book_prices_and_snap_fields_are_inapplicable() -> None:
    result = targets_slate_line(_source())

    for field in (
        "opponent_position_average", "opponent_adjustment_pct", "opponent_sample_games", "usage_adjustment_pct",
        "usage_sample_games", "book_probability", "book_count", "book_includes_margin", "book_fetched_at",
        "book_probability_devigged", "snap_share", "snap_share_games",
    ):
        assert getattr(result, field) is None


def test_a_missing_line_keeps_the_projection_without_a_gap_or_probability() -> None:
    result = targets_slate_line(replace(_source(), line=None))

    assert result.projection == 3.25 and result.line is None and result.edge is None
    assert (result.p_over, result.p_under, result.over_probability_version) == (None, None, None)


def test_hidden_fit_never_reads_a_table_even_if_quantiles_are_available() -> None:
    source = _source()
    assert targets_over_probability(source, project_targets(source.input), tables={"WR": QUANTILES}) is None


def test_a_shown_compatible_synthetic_fit_is_read_without_fitting_or_scoring() -> None:
    source = _source(tuple(_game(index, 4) for index in range(1, 5)))

    result = targets_over_probability(source, project_targets(source.input), shown=True, tables={"WR": QUANTILES})

    assert result is not None
    assert result.p_over == pytest.approx(0.4375) and result.p_under == pytest.approx(0.5625)


@pytest.mark.parametrize("tables", [{}, {"RB": QUANTILES}, {"WR": ()}])
def test_missing_position_or_empty_tables_supply_no_probability(tables: dict[str, tuple[float, ...]]) -> None:
    source = _source()
    assert targets_over_probability(source, project_targets(source.input), shown=True, tables=tables) is None


def test_a_fit_from_another_projection_version_supplies_no_probability() -> None:
    source = _source()
    assert targets_over_probability(source, project_targets(source.input), shown=True,
                                    fit_version="nfl-targets-v0", tables={"WR": QUANTILES}) is None


@pytest.mark.parametrize("history", [(), DEFAULT_HISTORY[:3], tuple(_game(index, 0) for index in range(1, 5))])
def test_missing_thin_and_zero_baselines_supply_no_ratio_probability(history: tuple[TargetsHistoryGame, ...]) -> None:
    source = _source(history)
    assert targets_over_probability(source, project_targets(source.input), shown=True, tables={"WR": QUANTILES}) is None


@pytest.mark.parametrize("line", [None, 4.0, -0.5, float("nan"), float("inf")])
def test_unreadable_lines_supply_no_probability(line: float | None) -> None:
    source = replace(_source(), line=line)
    assert targets_over_probability(source, project_targets(source.input), shown=True, tables={"WR": QUANTILES}) is None


@pytest.mark.parametrize(("field", "value"), [
    ("market", "receptions"), ("position", "QB"), ("segment", "first_half"), ("odds_type", "demon"),
])
def test_unsupported_rows_cannot_be_assembled_or_given_probabilities(field: str, value: str) -> None:
    source = replace(_source(), **{field: value})
    assert targets_over_probability(source, project_targets(source.input), shown=True, tables={"WR": QUANTILES}) is None
    with pytest.raises(ValueError, match="Rec Targets requires"):
        targets_slate_line(source)


@pytest.mark.parametrize("week", [0, 19])
def test_non_regular_season_weeks_cannot_be_assembled(week: int) -> None:
    source = _source()
    with pytest.raises(ValueError, match="weeks 1-18"):
        targets_slate_line(replace(source, input=replace(source.input, week=week)))


def test_serialization_freezes_targets_identity_and_evidence_with_no_served_probability_version() -> None:
    line = targets_slate_line(_source())

    frozen = prediction_row(line, NOW)
    payload = line.model_dump(by_alias=True)

    assert (payload["projectionModelVersion"], payload["pOver"], payload["pUnder"], payload["overProbabilityVersion"]) == (
        "nfl-targets-v1", None, None, None,
    )
    assert (frozen.prop_line_id, frozen.model_version, frozen.over_probability_version) == (70, "nfl-targets-v1", None)
    assert (frozen.projection, frozen.edge, frozen.p_over, frozen.p_under) == (3.25, -1.25, None, None)
    assert frozen.generated_at == NOW < KICKOFF and FETCHED < KICKOFF
    assert frozen.quality_flags == ["historical_baseline"]
    assert frozen.feature_snapshot == {
        "games_in_sample": 4, "baseline_season": 2026, "baseline_reason": "current_season",
        "opponent_adjustment_pct": None, "usage_adjustment_pct": None,
        "line": 4.5, "odds_type": "standard", "market": "receiving_targets", "segment": "full_game",
        "line_fetched_at": FETCHED.isoformat(),
    }


def test_no_baseline_is_still_a_truthful_serializable_record() -> None:
    frozen = prediction_row(targets_slate_line(_source(())), NOW)

    assert (frozen.projection, frozen.edge, frozen.p_over, frozen.over_probability_version) == (None, None, None, None)
    assert frozen.feature_snapshot["games_in_sample"] == 0
    assert frozen.feature_snapshot["baseline_season"] is None
    assert frozen.feature_snapshot["baseline_reason"] == "no_data"
    assert frozen.quality_flags == ["historical_baseline", "no_baseline"]
