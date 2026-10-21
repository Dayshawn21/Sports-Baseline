from dataclasses import replace
from datetime import date

import pytest

from app.core.nba_season import NBA_TEAM_CODES
from app.core.nba_team_stats import TEAM_STATS, TeamBoxGame, TeamBoxSide, TeamStatRate, team_stats

BEFORE = date(2026, 11, 1)


def _side(team: str, opponent: str, points: int = 100, **fields: int | None) -> TeamBoxSide:
    return TeamBoxSide(team, opponent, 10, {
        "points": points, "rebounds": fields.get("rebounds", 40), "assists": fields.get("assists", 20),
        "threes_made": fields.get("threes_made", 10), "blocks": fields.get("blocks", 5),
    })


def _game(home: str = "BOS", away: str = "NY", home_points: int = 100, away_points: int = 90) -> TeamBoxGame:
    return TeamBoxGame(2026, date(2026, 10, 25), home, away, home_points, away_points,
                       (_side(home, away, home_points), _side(away, home, away_points)))


def test_rates_pair_opponent_totals_and_use_each_teams_games() -> None:
    first = _game(home_points=110, away_points=95)
    first = replace(first, sides=(
        _side("BOS", "NY", 110, rebounds=48, assists=30, threes_made=15, blocks=7),
        _side("NY", "BOS", 95, rebounds=38, assists=18, threes_made=9, blocks=3),
    ))
    stats = team_stats([first, _game("BOS", "LAL", 100, 90)], 2026, BEFORE)
    assert stats["BOS"].completed_games == 2
    assert stats["NY"].completed_games == 1
    for stat, offense, allowed in zip(TEAM_STATS, (105, 44, 25, 12.5, 6), (92.5, 39, 19, 9.5, 4)):
        assert stats["BOS"].stats[stat].for_.per_game == offense
        assert stats["BOS"].stats[stat].allowed.per_game == allowed
        assert stats["BOS"].stats[stat].for_.games == 2
    assert stats["NY"].stats["points"].allowed.per_game == 110
    assert stats["NY"].stats["points"].for_.games == 1


@pytest.mark.parametrize("change", [
    {"season": 2025}, {"game_date": BEFORE}, {"game_date": date(2026, 11, 2)},
    {"game_type": "PRE"}, {"game_type": "PIN"}, {"game_type": "PST"},
    {"status": "scheduled"}, {"status": "postponed"}, {"status": "canceled"},
    {"sport": "nfl"}, {"home_team": "FOREIGN"}, {"home_team": "NY"},
])
def test_only_same_season_completed_regular_games_before_eastern_date_count(change: dict[str, object]) -> None:
    stats = team_stats([replace(_game(), **change)], 2026, BEFORE)
    assert all(team.completed_games == 0 for team in stats.values())
    assert all(pair.for_ == TeamStatRate(None, None, 0, 0) for team in stats.values() for pair in team.stats.values())


def test_dnp_groups_do_not_invalidate_played_totals() -> None:
    game = _game()
    dnp = TeamBoxSide("BOS", "NY", 3, {stat: None for stat in TEAM_STATS}, did_not_play=True)
    stats = team_stats([replace(game, sides=(*game.sides, dnp))], 2026, BEFORE)
    assert stats["BOS"].stats["points"].for_.per_game == 100
    assert stats["BOS"].stats["rebounds"].allowed.per_game == 40


@pytest.mark.parametrize("invalid", [None, -1])
def test_incomplete_stat_excludes_both_sides_only_for_that_metric(invalid: int | None) -> None:
    partial = _game()
    partial = replace(partial, sides=(_side("BOS", "NY", blocks=invalid), partial.sides[1]))
    good = _game()
    good = replace(good, sides=(_side("BOS", "NY", blocks=0), _side("NY", "BOS", 90, blocks=2)))
    stats = team_stats([partial, good], 2026, BEFORE)
    for team in ("BOS", "NY"):
        assert stats[team].completed_games == 2
        assert stats[team].stats["points"].for_.games == 2
        assert stats[team].stats["blocks"].for_.games == stats[team].stats["blocks"].allowed.games == 1
    assert stats["BOS"].stats["blocks"].for_ == TeamStatRate(0.0, 2, 1, 2)
    assert stats["NY"].stats["blocks"].allowed == TeamStatRate(0.0, 1, 1, 2)


@pytest.mark.parametrize("malformation", [
    "missing_side", "third_team", "wrong_opponent", "duplicate_side", "no_players",
    "null_points", "negative_points", "score_mismatch", "null_score", "all_dnp",
])
def test_invalid_boxes_preserve_completed_count_but_supply_no_rates(malformation: str) -> None:
    game = _game()
    home, away = game.sides
    if malformation == "missing_side":
        game = replace(game, sides=(home,))
    elif malformation == "third_team":
        game = replace(game, sides=(home, away, _side("LAL", "NY")))
    elif malformation == "wrong_opponent":
        game = replace(game, sides=(replace(home, opponent="LAL"), away))
    elif malformation == "duplicate_side":
        game = replace(game, sides=(home, away, home))
    elif malformation == "no_players":
        game = replace(game, sides=(replace(home, player_rows=0), away))
    elif malformation in ("null_points", "negative_points"):
        points = None if malformation == "null_points" else -1
        game = replace(game, sides=(replace(home, totals={**home.totals, "points": points}), away))
    elif malformation == "score_mismatch":
        game = replace(game, home_score=101)
    elif malformation == "null_score":
        game = replace(game, away_score=None)
    else:
        game = replace(game, sides=(replace(home, did_not_play=True), replace(away, did_not_play=True)))
    stats = team_stats([game], 2026, BEFORE)
    assert stats["BOS"].completed_games == stats["NY"].completed_games == 1
    assert all(pair.for_.per_game is None and pair.allowed.per_game is None
               for team in stats.values() for pair in team.stats.values())


def test_missing_boxes_count_as_partial_coverage_without_zero_filling() -> None:
    game = _game()
    stats = team_stats([game, replace(game, sides=())], 2026, BEFORE)
    assert stats["BOS"].completed_games == 2
    assert stats["BOS"].stats["points"].for_ == TeamStatRate(100.0, 1, 1, 2)


def test_league_ranks_include_teams_outside_target_matchup_with_competition_ties() -> None:
    stats = team_stats([_game("BOS", "NY", 100, 100), _game("LAL", "GS", 90, 80)], 2026, BEFORE)
    assert [stats[team].stats["points"].for_.rank for team in ("BOS", "NY", "LAL", "GS")] == [1, 1, 3, 4]
    assert [stats[team].stats["points"].allowed.rank for team in ("BOS", "NY", "LAL", "GS")] == [3, 3, 1, 2]
    assert stats["BOS"].stats["points"].for_.ranked_teams == 4
    assert stats["CHI"].stats["points"].for_ == TeamStatRate(None, None, 0, 4)


def test_ranks_tie_at_display_precision_and_population_is_metric_specific() -> None:
    games = []
    for index in range(30):
        home = _side("BOS", "NY", blocks=1 if index == 0 else 0)
        away = _side("NY", "BOS", 90, blocks=0)
        games.append(replace(_game(), sides=(home, away)))
    games.append(replace(_game("LAL", "GS"), sides=(
        _side("LAL", "GS", blocks=None), _side("GS", "LAL", 90),
    )))
    stats = team_stats(games, 2026, BEFORE)
    for team in ("BOS", "NY"):
        assert stats[team].stats["blocks"].for_ == TeamStatRate(0.0, 1, 30, 2)
    assert stats["LAL"].stats["blocks"].for_ == TeamStatRate(None, None, 0, 2)
    assert stats["LAL"].stats["points"].for_.ranked_teams == 4


def test_opening_day_never_falls_back_to_previous_season() -> None:
    stats = team_stats([replace(_game(), season=2025, game_date=date(2026, 4, 1))], 2026, date(2026, 10, 20))
    assert set(stats) == NBA_TEAM_CODES
    assert all(team.completed_games == 0 for team in stats.values())
    assert all(pair.for_ == pair.allowed == TeamStatRate(None, None, 0, 0)
               for team in stats.values() for pair in team.stats.values())


def test_empty_history_and_reversed_input_order_are_deterministic() -> None:
    assert len(team_stats([], 2026, BEFORE)) == 30
    games = [_game(), _game("GS", "LAL", 115, 110)]
    assert team_stats(games, 2026, BEFORE) == team_stats(reversed(games), 2026, BEFORE)
