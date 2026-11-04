import datetime as dt

import pytest

from app.core.nhl_player_values import GOALIE_MARKETS
from app.core.nhl_projection import (
    OUT_INJURY_STATUSES, Availability, GoalieAvailability, NhlLineProjection, project_line,
)
from app.core.nhl_projection_backtest import ARMS, NHL_PROJECTION_REFERENCE_VERSION, REFERENCE_ARM, NhlHistoryRow
from app.nhl.markets import NhlLineOnlyMarket

PLAYER = 1
CONFIRMED = Availability(goalie=GoalieAvailability("confirmed", "fresh", PLAYER))


def project(
    prior: list[NhlHistoryRow], market: NhlLineOnlyMarket, line: float, position: str | None,
    availability: Availability = CONFIRMED,
) -> NhlLineProjection:
    return project_line(prior, market, line, position, PLAYER, availability)


SKATER_STATS = {
    "goals": 1, "assists": 2, "points": 3, "shots": 4, "power_play_points": 1, "blocked_shots": 2,
    "plus_minus": -1, "hits": 3, "faceoffs_won": 8, "time_on_ice_seconds": 1200,
}
GOALIE_STATS = {"saves": 25, "goals_against": 2, "time_on_ice_seconds": 3600}
SKATER_MARKETS = [market for market in NhlLineOnlyMarket if market not in GOALIE_MARKETS]


def row(index: int, stats: dict[str, int | None], *, goalie: bool = False, started: bool = True) -> NhlHistoryRow:
    return NhlHistoryRow(
        player_id=1, game_id=index, season=2025, game_date=dt.date(2025, 11, 1) + dt.timedelta(days=index),
        game_type="REG", position="G" if goalie else "C", is_goalie=goalie, started=started, stats=stats,
    )


def skater_games(count: int, **overrides: int | None) -> list[NhlHistoryRow]:
    return [row(index, {**SKATER_STATS, **overrides, "shots": index % 7}) for index in range(count)]


def goalie_games(count: int) -> list[NhlHistoryRow]:
    return [row(index, {**GOALIE_STATS, "saves": 20 + index}, goalie=True) for index in range(count)]


@pytest.mark.parametrize("market", SKATER_MARKETS)
def test_skater_value_equals_the_backtested_reference_arm(market: NhlLineOnlyMarket) -> None:
    prior = skater_games(25)
    served = project(prior, market, 2.5, "C")
    assert served.projection == ARMS[REFERENCE_ARM](prior, market)
    assert served.flags == ()
    assert served.games_in_sample == 20


@pytest.mark.parametrize("market", sorted(GOALIE_MARKETS))
def test_goalie_value_equals_the_backtested_reference_arm(market: NhlLineOnlyMarket) -> None:
    prior = goalie_games(8)
    served = project(prior, market, 24.5, "G")
    assert served.projection == ARMS[REFERENCE_ARM](prior, market)
    assert served.prior_toi_minutes is None


def test_a_null_stat_game_is_skipped_not_counted_as_zero() -> None:
    prior = skater_games(12)
    prior[-1] = row(99, {**SKATER_STATS, "shots": None})
    served = project(prior, NhlLineOnlyMarket.SHOTS_ON_GOAL, 3.5, "C")
    assert served.games_in_sample == 11
    assert served.projection == ARMS[REFERENCE_ARM](prior, NhlLineOnlyMarket.SHOTS_ON_GOAL)


def test_nine_prior_games_is_too_few_and_ten_is_enough() -> None:
    assert project(skater_games(9), NhlLineOnlyMarket.HITS, 1.5, "C").flags == ("few_prior_games",)
    assert project(skater_games(10), NhlLineOnlyMarket.HITS, 1.5, "C").flags == ()


def test_toi_floor_is_inclusive_at_twelve_minutes() -> None:
    below = project(skater_games(10, time_on_ice_seconds=719), NhlLineOnlyMarket.HITS, 1.5, "C")
    at_floor = project(skater_games(10, time_on_ice_seconds=720), NhlLineOnlyMarket.HITS, 1.5, "C")
    assert (below.projection, below.flags) == (None, ("low_toi",))
    assert at_floor.flags == ()


def test_missing_toi_everywhere_is_low_toi_not_a_pass() -> None:
    served = project(skater_games(12, time_on_ice_seconds=None), NhlLineOnlyMarket.HITS, 1.5, "C")
    assert (served.projection, served.prior_toi_minutes, served.flags) == (None, None, ("low_toi",))


def test_a_goalie_counts_starts_only() -> None:
    games = goalie_games(4) + [row(50, GOALIE_STATS, goalie=True, started=False)]
    assert project(games, NhlLineOnlyMarket.GOALIE_SAVES, 24.5, "G").flags == ("few_prior_games",)
    assert project(goalie_games(5), NhlLineOnlyMarket.GOALIE_SAVES, 24.5, "G").flags == ()


@pytest.mark.parametrize("position", ["W", "D", None])
def test_faceoffs_won_is_for_centers_only(position: str | None) -> None:
    served = project(skater_games(12), NhlLineOnlyMarket.FACEOFFS_WON, 7.5, position)
    assert (served.projection, served.gap, served.flags) == (None, None, ("not_center",))


def test_a_center_gets_faceoffs_won() -> None:
    assert project(skater_games(12), NhlLineOnlyMarket.FACEOFFS_WON, 7.5, "C").projection == 8.0


def test_gap_is_projection_minus_line_rounded() -> None:
    served = project(skater_games(12, hits=3), NhlLineOnlyMarket.HITS, 3.55, "C")
    assert served.projection == 3.0
    assert served.gap == -0.55


def test_version_is_the_registered_reference_version() -> None:
    served = project(skater_games(12), NhlLineOnlyMarket.HITS, 1.5, "C")
    assert served.model_version == NHL_PROJECTION_REFERENCE_VERSION == "nhl-reference-v1"


def test_ineligible_line_still_reports_its_sample() -> None:
    served = project(skater_games(6), NhlLineOnlyMarket.HITS, 1.5, "C")
    assert (served.projection, served.games_in_sample) == (None, 6)


def goalie_line(goalie: GoalieAvailability | None) -> NhlLineProjection:
    return project(goalie_games(8), NhlLineOnlyMarket.GOALIE_SAVES, 24.5, "G", Availability(goalie=goalie))


@pytest.mark.parametrize("status", ["confirmed", "expected"])
def test_a_fresh_confirmed_or_expected_report_naming_him_serves_the_number(status: str) -> None:
    served = goalie_line(GoalieAvailability(status, "fresh", PLAYER))
    assert served.projection is not None
    assert served.flags == ()


@pytest.mark.parametrize(("goalie", "flag"), [
    (None, "no_goalie_report"),
    (GoalieAvailability("unavailable", "fresh", None), "no_goalie_report"),
    (GoalieAvailability("not_reported", "fresh", None), "no_goalie_report"),
    (GoalieAvailability("confirmed", "unavailable", PLAYER), "no_goalie_report"),
    (GoalieAvailability("confirmed", "stale", PLAYER), "context_stale"),
    (GoalieAvailability("unknown", "stale", None), "context_stale"),
    (GoalieAvailability("unknown", "fresh", PLAYER), "starter_unconfirmed"),
    (GoalieAvailability("confirmed", "fresh", None), "starter_unconfirmed"),
    (GoalieAvailability("confirmed", "fresh", 2), "other_starter_expected"),
    (GoalieAvailability("expected", "fresh", 2), "other_starter_expected"),
])
def test_a_goalie_line_without_a_usable_starter_report_has_no_number(
    goalie: GoalieAvailability | None, flag: str,
) -> None:
    served = goalie_line(goalie)
    assert (served.projection, served.gap, served.flags) == (None, None, (flag,))
    assert served.games_in_sample == 8


@pytest.mark.parametrize("freshness", ["fresh", "unavailable"])
def test_a_skater_with_no_injury_entry_is_served_without_flags(freshness: str) -> None:
    served = project(skater_games(12), NhlLineOnlyMarket.HITS, 1.5, "C", Availability(injury_freshness=freshness))
    assert (served.projection, served.flags) == (3.0, ())


@pytest.mark.parametrize("status", sorted(OUT_INJURY_STATUSES))
@pytest.mark.parametrize("freshness", ["fresh", "stale"])
def test_an_out_type_injury_entry_removes_the_number(status: str, freshness: str) -> None:
    served = project(skater_games(12), NhlLineOnlyMarket.HITS, 1.5, "C", Availability(None, status, freshness))
    assert (served.projection, served.gap, served.flags) == (None, None, ("injured_out",))
    assert served.games_in_sample == 12


def test_a_day_to_day_entry_is_served_with_a_flag() -> None:
    served = project(skater_games(12), NhlLineOnlyMarket.HITS, 1.5, "C", Availability(None, "Day-To-Day", "fresh"))
    assert (served.projection, served.flags) == (3.0, ("injury_listed",))


def test_a_stale_injury_snapshot_serves_the_number_with_a_flag() -> None:
    listed = project(skater_games(12), NhlLineOnlyMarket.HITS, 1.5, "C", Availability(None, "Day-To-Day", "stale"))
    assert listed.flags == ("injury_listed", "injury_context_stale")
    bare = project(skater_games(12), NhlLineOnlyMarket.HITS, 1.5, "C", Availability(None, None, "stale"))
    assert (bare.projection, bare.flags) == (3.0, ("injury_context_stale",))


def test_out_type_statuses_are_the_stored_espn_vocabulary_and_exclude_day_to_day() -> None:
    assert OUT_INJURY_STATUSES == {"Out", "Injured Reserve", "Suspension"}
    assert "Day-To-Day" not in OUT_INJURY_STATUSES


def test_eligibility_flag_wins_over_the_gate() -> None:
    served = project(skater_games(3), NhlLineOnlyMarket.HITS, 1.5, "C", Availability(None, "Out", "fresh"))
    assert served.flags == ("few_prior_games",)
