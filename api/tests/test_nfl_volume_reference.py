from datetime import UTC, datetime

import pytest

from app.core.nfl_volume_anchor import NFL_VOLUME_ANCHOR_PARAMETERS, AnchorRefused, anchored_probability
from app.core.nfl_volume_projection import (
    NFL_VOLUME_V1_PARAMETERS,
    NO_HISTORY,
    PlayerGame,
    game_context,
    project_player,
)
from app.repositories.nfl_volume_serving import VolumeServingLine
from app.schemas.nfl import NflHistorySampleSchema, NflSlateLineSchema
from app.services.nfl import volume
from app.services.nfl.prop_predictions import volume_prediction_row

NOW = datetime(2026, 11, 12, 15, tzinfo=UTC)
FETCHED = datetime(2026, 11, 12, 14, 58, tzinfo=UTC)
EMPTY = NflHistorySampleSchema(average=None, values=[])


def _game(season: int, week: int, targets: float, receptions: float) -> PlayerGame:
    return PlayerGame(
        season, week, {"targets": targets, "receptions": receptions, "receiving_yards": 50.0},
        team_pass_attempts=34.0, team_rush_attempts=26.0,
    )


HISTORY = (
    _game(2025, 16, 7.0, 5.0), _game(2025, 17, 9.0, 6.0),
    _game(2026, 6, 8.0, 5.0), _game(2026, 7, 6.0, 4.0), _game(2026, 8, 10.0, 7.0), _game(2026, 9, 7.0, 5.0),
)


def _row(**overrides: object) -> VolumeServingLine:
    fields: dict = {
        "line_id": 900, "game_id": 50, "player_id": 7, "player_name": "A Receiver", "position": "WR",
        "season": 2026, "week": 10, "player_team_id": 11, "opponent_team_id": 12, "is_home": True,
        "start_utc": datetime(2026, 11, 13, 1, 15, tzinfo=UTC), "market": "receptions", "segment": "full_game",
        "odds_type": "standard", "line": 5.5, "provider": "prizepicks", "fetched_at": FETCHED,
        "home_spread_margin": -3.5, "total": 44.5, "history": HISTORY,
    } | overrides
    return VolumeServingLine(**fields)


def test_the_reference_equals_project_player_and_the_frozen_anchor() -> None:
    row = _row()
    reference = volume.volume_reference(row)
    game = game_context(2026, 10, -3.5, 44.5, True)
    distribution = project_player("WR", HISTORY, game, NFL_VOLUME_V1_PARAMETERS).distributions["receptions"]
    at_line = distribution.p_over(5.5)
    q_vol = at_line.over / (at_line.over + at_line.under)
    anchor = NFL_VOLUME_ANCHOR_PARAMETERS
    over, under = anchored_probability(q_vol, at_line.push, anchor.a, anchor.b)

    assert reference is not None
    assert reference.projection == round(distribution.mean, 2)
    assert reference.median == distribution.median()
    assert reference.gap == round(reference.projection - 5.5, 2)
    assert (reference.q_vol, reference.p_over, reference.p_under, reference.p_push) == (q_vol, over, under, at_line.push)
    assert reference.games_in_sample == 6
    assert (reference.model_version, reference.over_probability_version) == ("nfl-volume-v1", "nfl-volume-anchor-v1")


def test_over_under_and_push_sum_to_one_and_the_anchor_pulls_toward_half() -> None:
    reference = volume.volume_reference(_row(line=5.0))
    assert reference is not None
    assert reference.p_over + reference.p_under + reference.p_push == pytest.approx(1.0)
    assert reference.p_push > 0
    raw_over = reference.q_vol * (1 - reference.p_push)
    assert abs(reference.p_over - 0.5 * (1 - reference.p_push)) < abs(raw_over - 0.5 * (1 - reference.p_push))


def test_the_flags_mark_a_gray_unvalidated_reference_and_a_thin_history() -> None:
    full = volume.volume_reference(_row())
    thin = volume.volume_reference(_row(history=HISTORY[-3:]))
    assert full is not None and thin is not None
    assert full.quality_flags == ["volume_reference", "anchor_unvalidated"]
    assert thin.games_in_sample == 3 and thin.quality_flags[-1] == "thin_history"


def test_a_zero_line_is_a_valid_line() -> None:
    reference = volume.volume_reference(_row(line=0.0))
    assert reference is not None and reference.line == 0.0


@pytest.mark.parametrize("overrides, reason", [
    ({"history": ()}, NO_HISTORY),
    ({"history": (_game(2024, 3, 8.0, 5.0),)}, NO_HISTORY),
    ({"home_spread_margin": None}, volume.NO_GAME_LINES),
    ({"total": None}, volume.NO_GAME_LINES),
    ({"is_home": None, "player_team_id": 99}, volume.NO_TEAM_SIDE),
    ({"line": None}, volume.NO_LINE),
    ({"line": -1.0}, volume.NO_LINE),
    ({"line": float("nan")}, volume.NO_LINE),
])
def test_missing_inputs_give_no_reference_and_a_reason_never_a_zero(overrides: dict, reason: str) -> None:
    row = _row(**overrides)
    assert volume.volume_reference(row) is None
    assert volume.volume_unavailable_reason(row) == reason


def test_a_reference_has_no_reason() -> None:
    assert volume.volume_unavailable_reason(_row()) is None


@pytest.mark.parametrize("overrides, error", [
    ({"position": "QB"}, ValueError),
    ({"market": "receiving_yards"}, AnchorRefused),
    ({"market": "passing_yards", "position": "QB"}, AnchorRefused),
    ({"segment": "first_half"}, ValueError),
    ({"odds_type": "alternate"}, ValueError),
    ({"odds_type": None}, ValueError),
    ({"week": 19}, ValueError),
])
def test_anything_the_model_was_not_adopted_for_is_refused(overrides: dict, error: type[Exception]) -> None:
    with pytest.raises(error):
        volume.volume_reference(_row(**overrides))


@pytest.mark.parametrize("odds_type", ["goblin", "demon"])
def test_a_rung_projects_exactly_as_a_standard_line_of_the_same_value_does(odds_type: str) -> None:
    standard = volume.volume_reference(_row(line=4.5))
    rung = volume.volume_reference(_row(odds_type=odds_type, line=4.5))

    assert rung is not None and rung == standard


def test_rungs_of_one_player_game_get_their_own_reference_at_their_own_line() -> None:
    references = [volume.volume_reference(_row(odds_type=kind, line=line)) for kind, line in (("goblin", 3.5), ("standard", 5.5), ("demon", 7.5))]

    assert all(reference is not None for reference in references)
    overs = [reference.p_over for reference in references if reference is not None]
    assert overs == sorted(overs, reverse=True) and len(set(overs)) == 3
    assert [reference.line for reference in references if reference is not None] == [3.5, 5.5, 7.5]


def test_the_input_history_is_not_mutated() -> None:
    history = list(HISTORY)
    volume.volume_reference(_row(history=tuple(history)))
    assert tuple(history) == HISTORY


def _v4_line() -> NflSlateLineSchema:
    return NflSlateLineSchema(
        line_id=900, player_id=7, player_name="A Receiver", position="WR", recent_form=EMPTY,
        opponent_history=EMPTY, opponent_allowed_history=EMPTY, market="receptions", segment="full_game",
        odds_type="standard", projection=5.1, line=5.5, edge=-0.4, games_in_sample=6, baseline_season=2026,
        baseline_reason="current_season", opponent_adjustment_pct=1.5, opponent_sample_games=17,
        usage_adjustment_pct=0.5, usage_sample_games=6, provider="prizepicks", fetched_at=FETCHED,
        projection_model_version="model-v4", quality_flags=["opponent_adjusted"],
        p_over=0.45, p_under=0.55, over_probability_version="nfl-pover-v1",
    )


def test_the_frozen_row_carries_the_volume_versions_and_the_raw_probability() -> None:
    reference = volume.volume_reference(_row())
    assert reference is not None
    row = volume_prediction_row(_v4_line(), reference, NOW)

    assert (row.prop_line_id, row.model_version, row.over_probability_version) == (900, "nfl-volume-v1", "nfl-volume-anchor-v1")
    assert (row.projection, row.p_over, row.p_under, row.edge) == (
        reference.projection, reference.p_over, reference.p_under, reference.gap,
    )
    assert row.generated_at == NOW and row.quality_flags == reference.quality_flags
    snapshot = row.feature_snapshot
    assert snapshot["q_vol"] == reference.q_vol and snapshot["median"] == reference.median
    assert snapshot["p_push"] == reference.p_push
    assert (snapshot["anchor_a"], snapshot["anchor_b"]) == (-0.0136, 0.4341)
    assert snapshot["line"] == 5.5 and snapshot["market"] == "receptions" and snapshot["odds_type"] == "standard"
    assert snapshot["line_fetched_at"] == "2026-11-12T14:58:00+00:00"


def test_the_frozen_row_does_not_fabricate_v4_adjustments() -> None:
    reference = volume.volume_reference(_row())
    assert reference is not None
    snapshot = volume_prediction_row(_v4_line(), reference, NOW).feature_snapshot
    assert snapshot["opponent_adjustment_pct"] is None and snapshot["usage_adjustment_pct"] is None
    assert snapshot["baseline_season"] is None and snapshot["baseline_reason"] == "nfl-volume-v1"
