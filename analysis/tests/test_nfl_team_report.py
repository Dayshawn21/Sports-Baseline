import numpy as np
import pandas as pd
import pytest

from lib import nfl_team_report as report


def games_frame(rows):
    """rows: (game_id, week, home, away, home_score, away_score, status)."""
    return pd.DataFrame(
        [(gid, 2026, week, home, away, hs, as_, status) for gid, week, home, away, hs, as_, status in rows],
        columns=["game_id", "season", "week", "home", "away", "home_score", "away_score", "status"],
    )


# Week 1: A beats B by 3, C ties D. Week 2: A loses to C by 20, D beats B by 3.
# Week 3: one game final, one still scheduled, so the cutoff is week 2.
GAMES = games_frame([
    (1, 1, "A", "B", 20, 17, "completed"),
    (2, 1, "C", "D", 10, 10, "completed"),
    (3, 2, "C", "A", 30, 10, "completed"),
    (4, 2, "D", "B", 24, 21, "completed"),
    (5, 3, "A", "D", 14, 7, "completed"),
    (6, 3, "B", "C", None, None, "scheduled"),
])


def test_last_final_week_stops_at_first_unfinished_week():
    assert report.last_final_week(GAMES, 2026) == 2


def test_last_final_week_counts_postponed_and_canceled_as_final():
    games = games_frame([(1, 1, "A", "B", None, None, "postponed"), (2, 2, "A", "B", None, None, "canceled")])
    assert report.last_final_week(games, 2026) == 2


def test_last_final_week_is_zero_before_any_final_week():
    assert report.last_final_week(GAMES, 2025) == 0


def test_team_games_has_both_sides_of_each_completed_game():
    rows = report.team_games(GAMES)
    assert len(rows) == 10
    a_week1 = rows[(rows.team == "A") & (rows.week == 1)].iloc[0]
    assert (a_week1.opponent, a_week1.is_home, a_week1.margin) == ("B", True, 3)
    b_week1 = rows[(rows.team == "B") & (rows.week == 1)].iloc[0]
    assert (b_week1.is_home, b_week1.margin) == (False, -3)


def test_standings_through_week_excludes_later_weeks():
    table = report.standings(GAMES, 2026, 2)
    a = table.loc["A"]
    assert (a.games, a.wins, a.losses, a.ties) == (2, 1, 1, 0)
    assert (a.points_for, a.points_against, a.point_diff) == (30, 47, -17)
    assert (a.one_score_wins, a.one_score_losses) == (1, 0)


def test_standings_counts_ties_and_one_score_losses():
    table = report.standings(GAMES, 2026, 2)
    assert table.loc["C", "ties"] == 1
    assert table.loc["B", "games"] == 2
    assert table.loc["B", "one_score_losses"] == 2


def test_pythagorean_wins_even_points_is_half_the_games():
    assert report.pythagorean_wins(200, 200, 6) == pytest.approx(3.0)


def test_pythagorean_wins_uses_the_nfl_exponent():
    expected = 30**2.37 / (30**2.37 + 20**2.37) * 2
    assert report.pythagorean_wins(30, 20, 2) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("pythagorean", "wins", "ties", "label"),
    [(3.75, 3, 0, "unlucky"), (3.74, 3, 0, "about right"), (2.25, 3, 0, "lucky"), (3.0, 2, 1, "about right"),
     (3.2, 2, 1, "about right"), (3.25, 2, 1, "unlucky")],
)
def test_luck_label_thresholds_count_ties_as_half(pythagorean, wins, ties, label):
    assert report.luck_label(pythagorean, wins, ties) == label


def test_rank_shares_the_better_rank_on_ties():
    ranks = report.rank(pd.Series([3, 1, 3, 0], index=list("ABCD")), best="high")
    assert ranks.to_dict() == {"A": 1, "B": 3, "C": 1, "D": 4}
    assert report.rank(pd.Series([0.1, -0.2]), best="low").tolist() == [2, 1]


GIVEAWAYS = pd.DataFrame(
    [(1, "A", 0), (1, "B", 2), (2, "C", 1), (2, "D", 1), (3, "C", 0), (3, "A", 3), (4, "D", 1), (4, "B", 0),
     (5, "A", 1), (5, "D", 2)],
    columns=["game_id", "team", "giveaways"],
)


def test_takeaways_are_the_opponents_giveaways_in_the_same_game():
    table = report.turnover_margins(GIVEAWAYS, GAMES, 2026, 1, 2)
    a = table.loc["A"]
    assert (a.giveaways, a.takeaways, a.margin) == (3, 2, -1)
    assert table.loc["C", "margin"] == 3
    assert table["margin_rank"].to_dict() == {"C": 1, "A": 2, "B": 2, "D": 2}


def test_turnover_margins_refuses_a_team_game_without_a_row():
    with pytest.raises(ValueError, match="not loaded"):
        report.turnover_margins(GIVEAWAYS[GIVEAWAYS.game_id != 4], GAMES, 2026, 1, 2)


def test_efficiency_ranks_offense_and_defense():
    efficiency = pd.DataFrame(
        [(1, "A", 10, 2.0, 5), (1, "B", 10, -1.0, 4), (2, "C", 10, 0.0, 5), (2, "D", 10, 0.0, 5)],
        columns=["game_id", "team", "plays", "epa", "successes"],
    )
    table = report.efficiency_ranks(efficiency, GAMES, 2026, 1)
    assert table.loc["A", "offense_epa"] == pytest.approx(0.2)
    assert table.loc["A", "defense_epa"] == pytest.approx(-0.1)
    assert table.loc["A", "offense_epa_rank"] == 1
    assert table.loc["A", "defense_epa_rank"] == 1
    assert table.loc["B", "defense_epa_rank"] == 4


def test_turnover_carryover_pairs_early_and_late_margins():
    games = games_frame([(1, 1, "A", "B", 1, 0, "completed"), (2, 2, "A", "B", 1, 0, "completed"),
                         (3, 1, "C", "D", 1, 0, "completed"), (4, 2, "C", "D", 1, 0, "completed")])
    giveaways = pd.DataFrame(
        [(1, "A", 0), (1, "B", 2), (2, "A", 0), (2, "B", 3), (3, "C", 1), (3, "D", 1), (4, "C", 1), (4, "D", 1)],
        columns=["game_id", "team", "giveaways"],
    )
    carry = report.turnover_carryover(giveaways, games, [2026], 1)
    assert carry.team_seasons == 4
    assert carry.correlation == pytest.approx(1.0)


def test_team_names_cover_every_team_with_a_nickname():
    assert len(report.TEAM_NAMES) == 32
    assert report.team_name("DAL") == "Dallas Cowboys"
    assert report.nickname("PHI") == "Eagles"


def test_bye_week_team_keeps_its_games_and_the_week_still_counts():
    games = games_frame([(1, 1, "A", "B", 7, 3, "completed"), (2, 1, "C", "D", 7, 3, "completed"),
                         (3, 2, "A", "B", 7, 3, "completed")])
    assert report.last_final_week(games, 2026) == 2
    table = report.standings(games, 2026, 2)
    assert table.loc["A", "games"] == 2
    assert table.loc["C", "games"] == 1


FIT = report.LeagueFit(slope=0.5, slope_team_seasons=0, home_edge=2.0, sigma=13.0)


@pytest.mark.parametrize(
    ("chance", "label"),
    [(0.35, "savable"), (0.3499, "long shot"), (0.10, "long shot"), (0.0999, "very unlikely"), (0.0, "very unlikely")],
)
def test_verdict_thresholds_are_fixed(chance, label):
    assert report.verdict(chance) == label


def test_shrink_slope_recovers_a_known_carryover():
    rows = []
    gid = 0
    for season in (2020, 2021):
        for week in (1, 2, 3, 4):
            # Through week 2 A beats B by 10; afterwards by 5, so half the margin carries over.
            gid += 1
            rows.append((gid, season, week, "A", "B", 10 if week <= 2 else 5, 0, "completed"))
    games = pd.DataFrame(rows, columns=["game_id", "season", "week", "home", "away", "home_score", "away_score",
                                        "status"])
    slope, team_seasons = report.shrink_slope(games, [2020, 2021], 2)
    assert slope == pytest.approx(0.5)
    assert team_seasons == 4


def test_home_edge_and_sigma_from_completed_games_only():
    edge, sigma = report.home_edge_and_sigma(GAMES, [2026])
    margins = pd.Series([3, 0, 20, 3, 7])
    assert edge == pytest.approx(margins.mean())
    assert sigma == pytest.approx(margins.std())


def test_win_chance_is_even_for_equal_teams_on_neutral_terms_and_symmetric():
    neutral = report.LeagueFit(0.5, 0, 0.0, 13.0)
    assert report.win_chance(1.0, 1.0, True, neutral) == pytest.approx(0.5)
    home = report.win_chance(3.0, 1.0, True, FIT)
    away = report.win_chance(1.0, 3.0, False, FIT)
    assert home + away == pytest.approx(1.0)
    assert home > 0.5


def test_remaining_games_are_after_the_cutoff_and_drop_canceled():
    games = games_frame([*GAMES.drop(columns="season").itertuples(index=False, name=None),
                         (7, 4, "A", "C", None, None, "canceled")])
    remaining = report.remaining_games(games, 2026, 2)
    assert sorted(remaining["game_id"].unique()) == [5, 6]
    assert set(remaining.loc[remaining.team == "A", "opponent"]) == {"D"}


def test_remaining_sos_ranks_the_hardest_schedule_first():
    remaining = pd.DataFrame({"game_id": [1, 1, 2, 2], "week": 3, "team": ["A", "B", "C", "D"],
                              "opponent": ["B", "A", "D", "C"], "is_home": [True, False, True, False]})
    sos = report.remaining_sos(remaining, pd.Series({"A": 5.0, "B": -5.0, "C": 1.0, "D": 0.0}))
    assert sos["rank"].to_dict() == {"B": 1, "D": 2, "C": 3, "A": 4}


def test_simulation_is_reproducible_with_the_seed():
    chances = [0.3, 0.6, 0.5]
    assert (report.simulate_wins(chances) == report.simulate_wins(chances)).all()


def test_a_certain_favorite_wins_every_game():
    assert (report.simulate_wins([1.0] * 11) == 11).all()
    assert (report.simulate_wins([0.0] * 11) == 0).all()


def test_simulated_wins_average_to_the_sum_of_chances():
    chances = [0.2, 0.4, 0.6, 0.8, 0.5]
    assert report.simulate_wins(chances).mean() == pytest.approx(sum(chances), abs=0.05)


def test_final_win_distribution_floors_half_wins_and_sums_to_one():
    distribution = report.final_win_distribution(2.5, np.array([0, 1, 1, 3]))
    assert distribution == {2: 0.25, 3: 0.5, 5: 0.25}


def test_playoff_chance_weights_each_total_by_its_rate():
    table = pd.DataFrame({"rate": [0.0, 0.5, 1.0]}, index=[8, 9, 10])
    assert report.playoff_chance({8: 0.5, 9: 0.25, 11: 0.25}, table) == pytest.approx(0.375)


def test_team_report_assembles_the_snapshot_and_simulation():
    efficiency = pd.DataFrame(
        [(gid, team, 10, 1.0, 5) for gid in (1, 2, 3, 4) for team in "ABCD"],
        columns=["game_id", "team", "plays", "epa", "successes"],
    )
    table = pd.DataFrame({"rate": [0.0, 1.0]}, index=[1, 3])
    result = report.team_report("A", 2026, 2, games=GAMES, efficiency=efficiency, giveaways=GIVEAWAYS,
                                playoff_table=table, fit=FIT)
    assert (result.wins, result.losses, result.remaining_games) == (1, 1, 1)
    assert result.turnover_margin == -1
    assert sum(result.final_win_distribution.values()) == pytest.approx(1.0)
    assert set(result.final_win_distribution) <= {1, 2}
    assert result.verdict == report.verdict(result.playoff_chance)


def test_team_report_refuses_a_team_without_games():
    with pytest.raises(ValueError, match="no completed games"):
        report.team_report("Z", 2026, 2, games=GAMES, efficiency=pd.DataFrame(), giveaways=GIVEAWAYS,
                           playoff_table=pd.DataFrame(), fit=FIT)
