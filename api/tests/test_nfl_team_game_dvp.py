import pytest

from app.core.nfl_projection import TEAM_GAME_DVP_MARKETS
from app.nfl.markets import NflPropMarket

from app.core.nfl_team_game_dvp import (
    DVP_TEAM_GAME_WINDOW, NflTeamGameTotals, apply_team_game_dvp, league_averages, team_game_inputs, window_averages,
)


def _game(game_id: int, receiving_yards: float, fantasy_points: float | None = 10.0) -> NflTeamGameTotals:
    return NflTeamGameTotals(
        game_id=game_id, season=2025, week=1, passing_yards=0.0, passing_attempts=0.0,
        passing_completions=0.0, rushing_yards=0.0, rushing_attempts=0.0,
        receiving_yards=receiving_yards, receptions=receiving_yards / 10, touchdowns=0.0,
        fantasy_points=fantasy_points,
    )


def test_window_takes_the_newest_seventeen_team_games_and_counts_games() -> None:
    newest_first = [_game(100 - i, 200.0) for i in range(DVP_TEAM_GAME_WINDOW)] + [_game(1, 0.0)] * 5

    averages = window_averages(newest_first)

    assert averages is not None
    assert averages["games"] == DVP_TEAM_GAME_WINDOW
    assert averages["receiving_yards"] == 200.0
    assert averages["receptions"] == 20.0


def test_window_uses_fewer_games_when_fewer_exist() -> None:
    averages = window_averages([_game(2, 150.0), _game(1, 100.0)])

    assert averages is not None
    assert (averages["games"], averages["receiving_yards"]) == (2, 125.0)


def test_fantasy_averages_only_known_games_and_stays_none_when_all_missing() -> None:
    partial = window_averages([_game(2, 100.0, 30.0), _game(1, 100.0, None)])
    missing = window_averages([_game(2, 100.0, None)])

    assert partial is not None and missing is not None
    assert (partial["games"], partial["fantasy_points"]) == (2, 30.0)
    assert missing["fantasy_points"] is None


def test_empty_input_has_no_averages() -> None:
    assert window_averages([]) is None
    assert league_averages({}) == {}


def test_league_pools_windows_so_a_full_defense_outweighs_a_thin_one() -> None:
    totals = {
        (1, "WR"): [_game(i, 200.0) for i in range(DVP_TEAM_GAME_WINDOW + 3)],
        (2, "WR"): [_game(i, 100.0) for i in range(3)],
        (1, "TE"): [_game(1, 50.0)],
    }

    league = league_averages(totals)

    expected = (DVP_TEAM_GAME_WINDOW * 200.0 + 3 * 100.0) / (DVP_TEAM_GAME_WINDOW + 3)
    assert league["WR"]["games"] == DVP_TEAM_GAME_WINDOW + 3
    assert league["WR"]["receiving_yards"] == pytest.approx(expected)
    assert (league["TE"]["games"], league["TE"]["receiving_yards"]) == (1, 50.0)


def test_team_game_inputs_pick_the_defense_window_and_the_position_league() -> None:
    totals = {(5, "WR"): [_game(2, 180.0), _game(1, 120.0)], (6, "WR"): [_game(3, 90.0)]}
    league = league_averages(totals)

    inputs = team_game_inputs(totals, league, 5, "WR")
    unknown_defense = team_game_inputs(totals, league, None, "WR")
    unseen_position = team_game_inputs(totals, league, 5, "TE")

    assert inputs["team_game_opponent_averages"] is not None
    assert inputs["team_game_opponent_averages"]["receiving_yards"] == 150.0
    assert inputs["team_game_league_averages"] == league["WR"]
    assert unknown_defense == {"team_game_opponent_averages": None, "team_game_league_averages": league["WR"]}
    assert unseen_position == {"team_game_opponent_averages": None, "team_game_league_averages": None}


def test_only_passing_completions_adopted_team_game_dvp() -> None:
    assert TEAM_GAME_DVP_MARKETS == frozenset({NflPropMarket.PASSING_COMPLETIONS})


@pytest.mark.parametrize("market", ["passing_attempts", "receiving_yards", "anytime_touchdown"])
def test_non_adopted_markets_keep_the_per_player_dvp(market: str) -> None:
    row = {"market": market, "opponent_averages": {"games": 51}, "team_game_opponent_averages": {"games": 17}}

    assert apply_team_game_dvp(row) is row


def test_adopted_market_swaps_in_the_team_game_averages() -> None:
    row = {
        "market": "passing_completions", "opponent_averages": {"games": 20}, "league_position_averages": {"games": 900},
        "team_game_opponent_averages": {"games": 17}, "team_game_league_averages": {"games": 540},
    }

    swapped = apply_team_game_dvp(row)

    assert swapped["opponent_averages"] == {"games": 17}
    assert swapped["league_position_averages"] == {"games": 540}
    assert row["opponent_averages"] == {"games": 20}
