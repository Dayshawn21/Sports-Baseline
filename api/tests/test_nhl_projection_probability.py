import datetime as dt

import pytest

from app.core import nhl_over_probability_fit as fit
from app.core import nhl_projection
from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core.nhl_over_probability_crossfit import read_family
from app.core.nhl_projection import Availability, GoalieAvailability, NhlLineProjection, over_read, project_line
from app.core.nhl_projection_backtest import NhlHistoryRow
from app.nhl.markets import NhlLineOnlyMarket

PLAYER = 1
CONFIRMED = Availability(goalie=GoalieAvailability("confirmed", "fresh", PLAYER))
SKATER = {
    "goals": 1, "assists": 2, "points": 3, "shots": 4, "power_play_points": 1, "blocked_shots": 2,
    "plus_minus": -1, "hits": 3, "faceoffs_won": 8, "time_on_ice_seconds": 1200,
}
GOALIE = {"saves": 25, "goals_against": 2, "time_on_ice_seconds": 3600}
HIDDEN = [market for market in NhlLineOnlyMarket if market.value not in fit.SHOWN_MARKETS]


def games(count: int, *, goalie: bool = False, **overrides: int | None) -> list[NhlHistoryRow]:
    base = GOALIE if goalie else SKATER
    return [
        NhlHistoryRow(
            player_id=PLAYER, game_id=index, season=2025, game_date=dt.date(2025, 11, 1) + dt.timedelta(days=index),
            game_type="REG", position="G" if goalie else "C", is_goalie=goalie, started=True,
            stats={**base, **overrides},
        )
        for index in range(count)
    ]


def project(market: NhlLineOnlyMarket, line: float, *, availability: Availability = CONFIRMED) -> NhlLineProjection:
    return project_line(games(25, goalie=market.value in ("goalie_saves", "goals_allowed")), market, line, "C", PLAYER, availability)


def test_shots_on_goal_reads_the_negative_binomial_from_the_fit() -> None:
    served = project(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5)
    assert served.projection == 4.0
    assert served.p_over == read_family(NegBinParams(fit.NEGBIN_R["shots_on_goal"]), 4.0, 3.5)
    assert served.over_probability_version == "nhl-pover-v1"


def test_time_on_ice_reads_the_scaled_normal_from_the_fit() -> None:
    served = project(NhlLineOnlyMarket.TIME_ON_ICE, 19.5)
    a, b = fit.SCALED_NORMAL["time_on_ice"]
    assert served.projection == 20.0
    assert served.p_over == read_family(ScaledNormalParams(a, b), 20.0, 19.5)


def test_goals_allowed_and_faceoffs_won_are_shown_markets() -> None:
    assert project(NhlLineOnlyMarket.GOALS_ALLOWED, 2.5).p_over is not None
    assert project(NhlLineOnlyMarket.FACEOFFS_WON, 7.5).p_over is not None


def test_p_under_is_the_complement_and_p_over_falls_as_the_line_rises() -> None:
    reads = [project(NhlLineOnlyMarket.SHOTS_ON_GOAL, line) for line in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 9.5)]
    probabilities = [served.p_over for served in reads]
    assert all(p is not None and 0 < p < 1 for p in probabilities)
    assert probabilities == sorted(probabilities, reverse=True)
    assert all(served.p_under == pytest.approx(1 - served.p_over) for served in reads if served.p_over is not None)


@pytest.mark.parametrize("market", [NhlLineOnlyMarket.SHOTS_ON_GOAL, NhlLineOnlyMarket.GOALS_ALLOWED])
def test_a_whole_number_line_reads_no_probability_but_names_the_fit(market: NhlLineOnlyMarket) -> None:
    served = project(market, 2.0)
    assert served.projection is not None
    assert (served.p_over, served.p_under) == (None, None)
    assert served.over_probability_version == "nhl-pover-v1"
    assert served.flags == ("integer_line",)


@pytest.mark.parametrize("market", HIDDEN)
def test_a_hidden_market_has_no_probability_and_no_new_flag(market: NhlLineOnlyMarket) -> None:
    served = project(market, 1.5)
    assert served.projection is not None
    assert (served.p_over, served.p_under, served.over_probability_version) == (None, None, None)
    assert served.flags == ()


def test_the_twelve_markets_split_into_the_four_shown_and_eight_hidden() -> None:
    assert {market.value for market in NhlLineOnlyMarket} >= fit.SHOWN_MARKETS
    assert len(HIDDEN) == len(NhlLineOnlyMarket) - 4


def test_a_gated_goalie_line_gets_no_probability() -> None:
    unconfirmed = Availability(goalie=GoalieAvailability("unknown", "fresh", None))
    served = project(NhlLineOnlyMarket.GOALS_ALLOWED, 2.5, availability=unconfirmed)
    assert served.projection is None
    assert (served.p_over, served.p_under, served.over_probability_version) == (None, None, None)
    assert served.flags == ("starter_unconfirmed",)


def test_an_injured_out_skater_gets_no_probability() -> None:
    out = Availability(injury_status="Out", injury_freshness="fresh")
    served = project(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5, availability=out)
    assert served.projection is None and served.p_over is None and served.flags == ("injured_out",)


def test_too_few_games_gets_no_probability() -> None:
    served = project_line(games(5), NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5, "C", PLAYER, Availability())
    assert served.projection is None and served.p_over is None and served.flags == ("few_prior_games",)


def test_a_listed_injury_still_shows_a_number_and_its_probability_under_the_same_note() -> None:
    listed = Availability(injury_status="Day-To-Day", injury_freshness="fresh")
    served = project(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5, availability=listed)
    assert served.p_over is not None
    assert served.flags == ("injury_listed",)


def test_a_fit_for_another_projection_version_serves_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fit, "FIT_PROJECTION_MODEL_VERSION", "nhl-reference-v2")
    served = project(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5)
    assert served.projection == 4.0
    assert (served.p_over, served.p_under, served.over_probability_version, served.flags) == (None, None, None, ())


def test_a_covered_market_with_no_parameters_flags_the_missing_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fit, "NEGBIN_R", {})
    served = project(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5)
    assert served.p_over is None and served.flags == ("no_over_probability",)


def test_an_unknown_family_flags_the_missing_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fit, "FAMILY_BY_MARKET", {**fit.FAMILY_BY_MARKET, "shots_on_goal": "ratio"})
    assert over_read(NhlLineOnlyMarket.SHOTS_ON_GOAL, 4.0, 3.5).flags == ("no_over_probability",)


@pytest.mark.parametrize("projection", [0.0, -1.0])
def test_a_non_positive_projection_reads_no_probability_without_raising(projection: float) -> None:
    read = over_read(NhlLineOnlyMarket.SHOTS_ON_GOAL, projection, 1.5)
    assert read.p_over is None and read.flags == ("no_over_probability",)


def test_the_served_projection_value_and_gap_are_unchanged_by_the_probability() -> None:
    served = project(NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5)
    assert served.gap == 0.5
    assert nhl_projection.NHL_PROJECTION_REFERENCE_VERSION == served.model_version


def test_the_served_fit_version_is_named_only_while_the_fit_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    assert nhl_projection.served_over_probability_version() == "nhl-pover-v1"
    monkeypatch.setattr(fit, "FIT_PROJECTION_MODEL_VERSION", "nhl-reference-v2")
    assert nhl_projection.served_over_probability_version() is None
