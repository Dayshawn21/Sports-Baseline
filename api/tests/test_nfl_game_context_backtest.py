from dataclasses import replace

import pytest

from app.backtest.nfl_game_context import (
    CONTEXT_ADOPTION_THRESHOLD,
    NflContextScore,
    adjustment,
    context_adopted,
    context_rows,
    fit_context,
    score_context,
)
from app.backtest.nfl_game_lines import FIT_SEASONS, HOLDOUT_SEASONS, build_cases
from app.core.nfl_elo import NFL_ELO_V1, NflEloGame
from app.core.nfl_game_lines import NflGameLineGame, PickRecord
from app.core.nfl_scoring_ratings import NflScoringConfig

ROOFS = ("outdoors", "dome", "outdoors", "open", "closed", None)


def _games() -> list[NflGameLineGame]:
    """Synthetic 2012-2025 schedule with varied roofs, weather, and rest."""
    teams = ["KC", "DEN", "LV", "LAC"]
    games: list[NflGameLineGame] = []
    for season in range(2012, 2026):
        for week in range(1, 9):
            for pair in range(2):
                seed = season * 31 + week * 7 + pair * 13
                home, away = teams[(week + pair) % 4], teams[(week + pair + 2) % 4]
                games.append(NflGameLineGame(
                    NflEloGame(f"{season}_{week}_{pair}", season, week, home, away, 14 + seed % 24, 10 + seed % 19),
                    float(seed % 7), 40.5 + seed % 9, -150, 130,
                    roof=ROOFS[seed % len(ROOFS)], temp=20 + seed % 60, wind=seed % 25,
                    home_rest=4 + seed % 11, away_rest=4 + (seed // 3) % 11,
                ))
    return games


def test_context_coefficients_do_not_change_when_every_holdout_outcome_is_flipped() -> None:
    games = _games()
    flipped = [
        replace(line_game, game=replace(
            line_game.game, home_score=(line_game.game.away_score or 0) + 30, away_score=line_game.game.home_score,
        )) if line_game.game.season in HOLDOUT_SEASONS else line_game
        for line_game in games
    ]

    assert fit_context(flipped) == fit_context(games)


def test_there_is_one_coefficient_per_published_feature_and_no_intercept_term() -> None:
    coefficients = fit_context(_games())

    assert len(coefficients["total"]) == 5
    assert len(coefficients["spread"]) == 1


def test_context_rows_pair_each_arm_with_its_own_line_and_outcome() -> None:
    game = NflGameLineGame(
        NflEloGame("g", 2014, 5, "KC", "DEN", 24, 17), 3.0, 44.5, -150, 130,
        roof="outdoors", temp=25, wind=18, home_rest=14, away_rest=7,
    )
    [case] = build_cases([game], NFL_ELO_V1, NflScoringConfig(0.1), FIT_SEASONS)

    assert context_rows([case], "total") == [([0.0, 18.0, 15.0, 0.0, 0.0], 44.5, 41.0)]
    assert context_rows([case], "spread") == [([7.0], 3.0, 7.0)]


def test_a_windy_under_adjustment_is_graded_as_an_under_pick() -> None:
    game = NflGameLineGame(
        NflEloGame("g", 2023, 5, "KC", "DEN", 13, 10), 3.0, 44.5, -150, 130,
        roof="outdoors", temp=50, wind=20, home_rest=7, away_rest=7,
    )
    [case] = build_cases([game], NFL_ELO_V1, NflScoringConfig(0.1), HOLDOUT_SEASONS)
    # -0.1 points per mph: 20 mph takes 2.0 points off a 44.5 total that landed on 23.
    coefficients = (0.0, -0.1, 0.0, 0.0, 0.0)

    score = score_context("set", [case], "total", coefficients)

    assert adjustment(coefficients, case.total_features.vector()) == pytest.approx(-2.0)
    assert score.picks[2.0] == PickRecord(1, 0, 0)
    assert score.adjusted_mae < score.market_mae


def _score(market_mae: float, adjusted_mae: float, record: PickRecord) -> NflContextScore:
    return NflContextScore("set", 1000, market_mae, adjusted_mae, {0.5: record, 1.0: record, 2.0: record})


@pytest.mark.parametrize(
    "adjusted_mae, record, expected",
    [
        (10.1, PickRecord(53, 47, 2), True),
        (10.1, PickRecord(52, 46, 0), False),  # 98 decided picks, under the minimum
        (10.1, PickRecord(52, 48, 0), False),  # 52.0% is under the 52.4% breakeven
        (10.2, PickRecord(80, 40, 0), False),  # no MAE improvement over the closing line
    ],
)
def test_context_rule(adjusted_mae: float, record: PickRecord, expected: bool) -> None:
    assert CONTEXT_ADOPTION_THRESHOLD == 0.5
    assert context_adopted(_score(10.2, adjusted_mae, record)) is expected
