import datetime as dt
from dataclasses import asdict

import pytest

from app.core import nhl_over_probability_fit as fit
from app.core.nhl_projection import Availability, GoalieAvailability, project_line
from app.core.nhl_projection_backtest import NHL_PROJECTION_REFERENCE_VERSION, NhlHistoryRow
from app.core.nhl_prop_predictions import NhlFreezeLine, frozen_actual, prediction_row, settle_frozen
from app.nhl.markets import NhlLineOnlyMarket

NOW = dt.datetime(2026, 10, 24, 17, 0, tzinfo=dt.UTC)
FETCHED = dt.datetime(2026, 10, 24, 16, 59, tzinfo=dt.UTC)
PLAYER = 7
SKATER_STATS = {
    "goals": 1, "assists": 2, "points": 3, "shots": 4, "power_play_points": 1, "blocked_shots": 2,
    "plus_minus": 0, "hits": 3, "faceoffs_won": 8, "time_on_ice_seconds": 1200,
}
GOALIE_STATS = {"saves": 25, "goals_against": 2, "time_on_ice_seconds": 3600}


def _history(games: int, goalie: bool = False) -> list[NhlHistoryRow]:
    stats = GOALIE_STATS if goalie else SKATER_STATS
    return [
        NhlHistoryRow(
            player_id=PLAYER, game_id=100 + day, season=2026, game_date=dt.date(2026, 10, 1) + dt.timedelta(days=day),
            game_type="REG", position="G" if goalie else "C", is_goalie=goalie, started=True,
            stats={**stats, "shots": 2 + day % 5, "faceoffs_won": 6 + day % 5},
        )
        for day in range(games)
    ]


def _line(market: NhlLineOnlyMarket, line: float, odds_type: str = "standard") -> NhlFreezeLine:
    return NhlFreezeLine(
        line_id=55, game_id=9, game_date=dt.date(2026, 10, 24), start_utc=NOW + dt.timedelta(hours=7),
        player_id=PLAYER, team="BOS", position="C", market=market.value, odds_type=odds_type, line=line,
        fetched_at=FETCHED,
    )


def _frozen(
    market: NhlLineOnlyMarket, line: float, games: int = 20, odds_type: str = "standard",
    availability: Availability = Availability(), goalie: bool = False,
):
    projection = project_line(_history(games, goalie), market, line, "G" if goalie else "C", PLAYER, availability)
    return projection, prediction_row(_line(market, line, odds_type), projection, NOW)


def test_a_shown_market_line_freezes_the_core_probabilities_unrounded() -> None:
    projection, row = _frozen(NhlLineOnlyMarket.SHOTS_ON_GOAL, 2.5)

    assert row.over_probability_version == fit.OVER_PROBABILITY_VERSION == "nhl-pover-v1"
    assert projection.p_over is not None and projection.p_under is not None
    assert (row.p_over, row.p_under) == (projection.p_over, projection.p_under)
    assert row.p_over != round(row.p_over, 4)
    assert row.p_over + row.p_under == pytest.approx(1.0)


def test_a_hidden_market_freezes_a_projection_and_no_probability() -> None:
    _, row = _frozen(NhlLineOnlyMarket.HITS, 2.5)

    assert NhlLineOnlyMarket.HITS.value not in fit.SHOWN_MARKETS
    assert row.projection is not None
    assert (row.p_over, row.p_under, row.over_probability_version) == (None, None, None)
    assert row.quality_flags == []


def test_a_whole_number_line_in_a_shown_market_freezes_no_probability_but_the_version() -> None:
    _, row = _frozen(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.0)

    assert row.projection is not None
    assert (row.p_over, row.p_under) == (None, None)
    assert row.over_probability_version == "nhl-pover-v1"
    assert row.quality_flags == ["integer_line"]


def test_a_gated_goalie_line_freezes_null_with_its_flag_and_sample() -> None:
    unconfirmed = Availability(goalie=GoalieAvailability("unknown", "fresh", None))
    _, row = _frozen(NhlLineOnlyMarket.GOALS_ALLOWED, 2.5, availability=unconfirmed, goalie=True)

    assert row.projection is None
    assert (row.p_over, row.p_under, row.over_probability_version) == (None, None, None)
    assert row.quality_flags == ["starter_unconfirmed"]
    assert row.feature_snapshot["games_in_sample"] == 20
    assert row.feature_snapshot["gap"] is None


def test_a_thin_sample_is_frozen_not_skipped() -> None:
    _, row = _frozen(NhlLineOnlyMarket.SHOTS_ON_GOAL, 2.5, games=5)

    assert row.projection is None
    assert row.quality_flags == ["few_prior_games"]


@pytest.mark.parametrize("odds_type", ["standard", "demon", "goblin"])
def test_every_odds_type_keeps_its_label_in_the_snapshot(odds_type: str) -> None:
    _, row = _frozen(NhlLineOnlyMarket.SHOTS_ON_GOAL, 2.5, odds_type=odds_type)

    assert row.feature_snapshot["odds_type"] == odds_type


def test_the_row_is_what_project_line_served() -> None:
    projection, row = _frozen(NhlLineOnlyMarket.SHOTS_ON_GOAL, 2.5)
    served = asdict(projection)

    assert row.prop_line_id == 55
    assert row.model_version == served["model_version"] == NHL_PROJECTION_REFERENCE_VERSION
    assert row.projection == served["projection"]
    assert row.edge is None
    assert row.quality_flags == list(served["flags"])
    assert row.generated_at == NOW
    assert row.feature_snapshot == {
        "games_in_sample": served["games_in_sample"], "prior_toi_minutes": served["prior_toi_minutes"],
        "gap": served["gap"], "line": 2.5, "odds_type": "standard", "market": "shots_on_goal",
        "segment": "full_game", "line_fetched_at": FETCHED.isoformat(),
    }


def _skater(**stats: int | None) -> dict[str, int | None]:
    return {**SKATER_STATS, **stats}


def _goalie(started: bool = True, **stats: int | None) -> dict[str, int | bool | None]:
    return {**GOALIE_STATS, "started": started, **stats}


def test_a_game_with_no_box_scores_is_not_loaded() -> None:
    assert settle_frozen("shots_on_goal", 2.5, None, None, game_has_box_scores=False) == "stats_not_loaded"


def test_a_skater_missing_from_a_loaded_game_is_void() -> None:
    assert settle_frozen("shots_on_goal", 2.5, None, None, game_has_box_scores=True) == "void_dnp"


def test_a_goalie_missing_or_not_starting_is_void() -> None:
    assert settle_frozen("goalie_saves", 24.5, None, None, game_has_box_scores=True) == "void_dnp"
    assert settle_frozen("goalie_saves", 24.5, None, _goalie(started=False), game_has_box_scores=True) == "void_dnp"


def test_a_row_missing_the_stat_is_not_a_call_never_zero() -> None:
    assert settle_frozen("faceoffs_won", 7.5, _skater(faceoffs_won=None), None, game_has_box_scores=True) == "missing_stat"


def test_over_and_under_against_the_line() -> None:
    assert settle_frozen("shots_on_goal", 3.5, _skater(shots=5), None, game_has_box_scores=True) == "over"
    assert settle_frozen("shots_on_goal", 3.5, _skater(shots=2), None, game_has_box_scores=True) == "under"
    assert settle_frozen("goalie_saves", 24.5, None, _goalie(saves=30), game_has_box_scores=True) == "over"
    assert settle_frozen("goals_allowed", 2.5, None, _goalie(goals_against=1), game_has_box_scores=True) == "under"


def test_time_on_ice_settles_in_minutes() -> None:
    row = _skater(time_on_ice_seconds=1050)
    assert settle_frozen("time_on_ice", 17.5, row, None, game_has_box_scores=True) == "push"
    assert settle_frozen("time_on_ice", 17.0, row, None, game_has_box_scores=True) == "over"


def test_a_whole_number_line_can_push() -> None:
    assert settle_frozen("hits", 3.0, _skater(hits=3), None, game_has_box_scores=True) == "push"


def test_a_goalie_market_reads_the_goalie_row_not_the_skater_row() -> None:
    assert settle_frozen("goalie_saves", 24.5, _skater(), _goalie(saves=20), game_has_box_scores=True) == "under"


def test_frozen_actual_reads_the_skater_value() -> None:
    assert frozen_actual("shots_on_goal", _skater(shots=5), None, game_has_box_scores=True) == 5


def test_frozen_actual_reads_time_on_ice_in_minutes() -> None:
    assert frozen_actual("time_on_ice", _skater(time_on_ice_seconds=1290), None, game_has_box_scores=True) == 21.5


def test_frozen_actual_reads_a_goalie_market_from_the_goalie_row() -> None:
    assert frozen_actual("goalie_saves", _skater(), _goalie(saves=31), game_has_box_scores=True) == 31


def test_frozen_actual_voids_a_goalie_who_did_not_start() -> None:
    assert frozen_actual("goals_allowed", None, _goalie(started=False), game_has_box_scores=True) == "void_dnp"


def test_frozen_actual_waits_for_an_unloaded_game() -> None:
    assert frozen_actual("points", _skater(), None, game_has_box_scores=False) == "stats_not_loaded"


def test_frozen_actual_never_reads_a_missing_stat_as_zero() -> None:
    assert frozen_actual("hits", _skater(hits=None), None, game_has_box_scores=True) == "missing_stat"
