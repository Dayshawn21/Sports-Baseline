import pytest

from app.core.nfl_efficiency_ratings import NflEfficiencyConfig, NflEfficiencyRow, efficiency_features, replay
from app.core.nfl_elo import NflEloGame

CONFIG = NflEfficiencyConfig(learning_rate=0.5)


def _game(key: str, week: int, home: str, away: str, season: int = 2024) -> NflEloGame:
    return NflEloGame(key, season, week, home, away, 20, 17)


# Week 1 only seeds the league average (0.1 here), so later weeks have a baseline.
SEED = [_game("s1", 1, "AAA", "BBB"), _game("s2", 1, "CCC", "DDD")]
SEED_METRIC = {("s1", True): 0.1, ("s1", False): 0.1, ("s2", True): 0.1, ("s2", False): 0.1}


def test_the_first_week_seeds_the_league_without_moving_any_rating() -> None:
    rows = replay([*SEED, _game("g", 2, "AAA", "CCC")], SEED_METRIC, CONFIG)

    assert rows[0].league is None and rows[0].expected_home is None
    assert rows[2].league == pytest.approx(0.1)
    assert (rows[2].home_offset, rows[2].away_offset) == (0.0, 0.0)


def test_a_strong_offense_rises_and_the_defense_it_faced_is_charged() -> None:
    games = [*SEED, _game("g", 2, "AAA", "BBB"), _game("n1", 3, "AAA", "CCC"), _game("n2", 3, "DDD", "BBB")]
    # AAA's offense beats the 0.1 league by 0.3; BBB's offense matches it exactly.
    metric = {**SEED_METRIC, ("g", True): 0.4, ("g", False): 0.1}

    rows = {row.game_key: row for row in replay(games, metric, CONFIG)}

    # At a 0.5 learning rate, AAA's offense and BBB's defense each move by 0.15.
    assert rows["n1"].home_offset == pytest.approx(0.15)
    # Whoever faces BBB next inherits its leaky defense; BBB's own offense is unchanged.
    assert rows["n2"].home_offset == pytest.approx(0.15)
    assert rows["n2"].away_offset == pytest.approx(0.0)


def test_offsets_regress_toward_zero_between_seasons() -> None:
    games = [*SEED, _game("g", 2, "AAA", "BBB"), _game("next", 1, "AAA", "CCC", season=2025)]
    metric = {**SEED_METRIC, ("g", True): 0.4, ("g", False): 0.1}

    rows = replay(games, metric, CONFIG)

    assert rows[-1].home_offset == pytest.approx(0.15 * (2 / 3))


def test_a_game_missing_either_side_updates_nothing() -> None:
    games = [*SEED, _game("g", 2, "AAA", "BBB"), _game("n", 3, "AAA", "BBB")]
    metric = {**SEED_METRIC, ("g", True): 0.9}

    rows = replay(games, metric, CONFIG)

    assert rows[-1].league == pytest.approx(0.1)
    assert (rows[-1].home_offset, rows[-1].away_offset) == (0.0, 0.0)


def test_games_in_the_same_week_cannot_see_each_other() -> None:
    games = [*SEED, _game("a", 2, "AAA", "BBB"), _game("b", 2, "CCC", "DDD"), _game("c", 3, "CCC", "AAA")]
    metric = {**SEED_METRIC, ("a", True): 0.9, ("a", False): 0.9}

    rows = {row.game_key: row for row in replay(games, metric, CONFIG)}

    assert rows["b"].league == pytest.approx(0.1)
    assert rows["b"].home_offset == 0.0
    # From week 3 the league includes game a's two team-games.
    assert rows["c"].league == pytest.approx((0.1 * 4 + 0.9 * 2) / 6)


def _row(home_offset: float, away_offset: float) -> NflEfficiencyRow:
    return NflEfficiencyRow("g", 2024, 5, 0.0, home_offset, away_offset)


def test_two_average_teams_give_all_zero_features() -> None:
    features = efficiency_features(_row(0.0, 0.0), _row(0.0, 0.0), _row(0.0, 0.0))

    assert features.spread_vector() == [0.0, 0.0]
    assert features.total_vector() == [0.0, 0.0, 0.0]


def test_a_better_home_offense_raises_the_edges_and_the_sums() -> None:
    features = efficiency_features(_row(0.1, -0.05), _row(0.04, 0.0), _row(0.0, 0.0))

    assert features.epa_edge == pytest.approx(0.15)
    assert features.success_edge == pytest.approx(0.04)
    assert features.epa_sum == pytest.approx(0.05)


def test_a_faster_pair_raises_pace_and_leaves_the_edges_alone() -> None:
    features = efficiency_features(_row(0.0, 0.0), _row(0.0, 0.0), _row(3.0, 2.5))

    assert features.pace == pytest.approx(5.5)
    assert features.spread_vector() == [0.0, 0.0]


def test_each_team_game_counts_once_in_the_league_average() -> None:
    # Plays is a metric too: the league average is the plain mean of team-game values.
    games = [_game("a", 1, "AAA", "BBB"), _game("b", 2, "AAA", "BBB")]

    rows = replay(games, {("a", True): 70.0, ("a", False): 50.0}, CONFIG)

    assert rows[1].league == pytest.approx(60.0)
    assert (rows[1].expected_home, rows[1].expected_away) == (pytest.approx(60.0), pytest.approx(60.0))
