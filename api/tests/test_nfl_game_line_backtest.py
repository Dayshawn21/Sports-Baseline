from dataclasses import replace

import pytest

from app.backtest.nfl_game_lines import (
    ADOPTION_MIN_PICKS,
    FIT_SEASONS,
    HOLDOUT_SEASONS,
    NflArmScore,
    adopted,
    arm_values,
    build_cases,
    fit,
    fit_blend_weight,
    week_bucket,
)
from app.core.nfl_elo import NFL_ELO_V1, NflEloGame, expected_home_win_probability, replay
from app.core.nfl_game_context import NflTotalFeatures
from app.core.nfl_game_lines import NflGameLineGame, PickRecord, elo_margin
from app.core.nfl_scoring_ratings import NflScoringConfig

SCORING = NflScoringConfig(learning_rate=0.1)


def _line_game(
    key: str, season: int, week: int, scores: tuple[int, int] | None,
    spread: float | None = 3.0, total: float | None = 44.5, moneylines: tuple[int | None, int | None] = (-160, 140),
) -> NflGameLineGame:
    home_score, away_score = scores if scores is not None else (None, None)
    return NflGameLineGame(
        NflEloGame(key, season, week, "KC", "DEN", home_score, away_score), spread, total, *moneylines,
    )


def test_fit_and_holdout_seasons_skip_burn_in_and_the_season_in_progress() -> None:
    assert (min(FIT_SEASONS), max(FIT_SEASONS)) == (2014, 2021)
    assert (min(HOLDOUT_SEASONS), max(HOLDOUT_SEASONS)) == (2022, 2025)
    assert not FIT_SEASONS & HOLDOUT_SEASONS


@pytest.mark.parametrize("week, bucket", [(1, "1-4"), (4, "1-4"), (5, "5+"), (18, "5+")])
def test_week_bucket(week: int, bucket: str) -> None:
    assert week_bucket(week) == bucket


def test_only_final_games_in_the_requested_seasons_become_cases() -> None:
    games = [
        _line_game("burn_in", 2013, 1, (20, 17)),
        _line_game("fit", 2014, 1, (24, 10)),
        _line_game("unplayed", 2014, 2, None),
        _line_game("in_progress_season", 2026, 1, (31, 3)),
    ]

    cases = build_cases(games, NFL_ELO_V1, SCORING, FIT_SEASONS | HOLDOUT_SEASONS)

    assert [case.game_key for case in cases] == ["fit"]


def test_a_case_carries_outcomes_and_pre_game_model_values_from_the_full_history() -> None:
    games = [_line_game("burn_in", 2013, 17, (35, 7)), _line_game("fit", 2014, 1, (24, 24))]

    [case] = build_cases(games, NFL_ELO_V1, SCORING, FIT_SEASONS)

    # The 2013 burn-in game still moved the ratings the 2014 case starts from.
    rows = replay([game.game for game in games])
    home_pre, away_pre = rows[2].elo_pre, rows[3].elo_pre
    assert home_pre != away_pre
    assert case.elo_home_probability == pytest.approx(expected_home_win_probability(home_pre, away_pre))
    assert case.elo_margin == pytest.approx(elo_margin(home_pre, away_pre, NFL_ELO_V1.home_field))
    assert (case.home_won, case.home_margin, case.total_points) == (None, 0, 48)
    assert case.week_bucket == "1-4"


def test_a_missing_line_blanks_only_its_own_market() -> None:
    games = [
        _line_game("no_spread", 2014, 5, (21, 14), spread=None),
        _line_game("no_total", 2014, 6, (21, 14), total=None),
        _line_game("no_moneyline", 2014, 7, (21, 14), moneylines=(None, 140)),
    ]

    no_spread, no_total, no_moneyline = build_cases(games, NFL_ELO_V1, SCORING, FIT_SEASONS)

    assert (no_spread.spread_line, no_spread.total_line) == (None, 44.5)
    assert no_spread.market_home_probability is not None
    assert (no_total.total_line, no_total.spread_line) == (None, 3.0)
    assert no_moneyline.market_home_probability is None
    assert (no_moneyline.spread_line, no_moneyline.total_line) == (3.0, 44.5)


def test_a_case_carries_context_features_for_a_dome_and_an_outdoor_game() -> None:
    dome = replace(_line_game("dome", 2014, 5, (27, 20)), roof="dome", temp=None, wind=None, home_rest=4, away_rest=4)
    outdoor = replace(_line_game("outdoor", 2014, 6, (13, 10)), roof="outdoors", temp=25, wind=18, home_rest=14, away_rest=7)

    dome_case, outdoor_case = build_cases([dome, outdoor], NFL_ELO_V1, SCORING, FIT_SEASONS)

    assert dome_case.total_features == NflTotalFeatures(1.0, 0.0, 0.0, 0.0, 1.0)
    assert dome_case.spread_features.rest_diff == 0.0
    assert outdoor_case.total_features == NflTotalFeatures(0.0, 18.0, 15.0, 0.0, 0.0)
    assert outdoor_case.spread_features.rest_diff == 7.0


def test_a_game_without_stored_context_is_weather_unknown() -> None:
    [case] = build_cases([_line_game("bare", 2014, 5, (27, 20))], NFL_ELO_V1, SCORING, FIT_SEASONS)

    assert case.total_features == NflTotalFeatures(0.0, 0.0, 0.0, 1.0, 0.0)


def test_arm_values_drop_a_tie_from_the_moneyline_arm_only() -> None:
    [tie] = build_cases([_line_game("tie", 2014, 5, (20, 20))], NFL_ELO_V1, SCORING, FIT_SEASONS)

    assert arm_values([tie], "moneyline") == ([], [], [])
    assert arm_values([tie], "spread")[2] == [0.0]
    assert arm_values([tie], "total")[2] == [40.0]


def test_a_blend_weight_tie_keeps_the_market() -> None:
    # Model equal to the market: every weight scores the same, so the smallest (0.0) wins.
    [case] = build_cases([_line_game("g", 2014, 5, (27, 20))], NFL_ELO_V1, SCORING, FIT_SEASONS)
    same_as_market = replace(case, elo_margin=3.0, spread_line=3.0)

    assert fit_blend_weight([same_as_market], "spread") == 0.0


def _season_of_games() -> list[NflGameLineGame]:
    teams = ["KC", "DEN", "LV", "LAC"]
    games: list[NflGameLineGame] = []
    for season in range(2012, 2026):
        for week in range(1, 7):
            for pair in range(2):
                home, away = teams[(week + pair) % 4], teams[(week + pair + 2) % 4]
                home_score = 17 + (season * 7 + week * 3 + pair * 5) % 21
                away_score = 10 + (season * 3 + week * 5 + pair * 11) % 24
                games.append(NflGameLineGame(
                    NflEloGame(f"{season}_{week}_{pair}", season, week, home, away, home_score, away_score),
                    float(week % 5), 44.5, -150, 130,
                ))
    return games


def test_the_fit_is_unchanged_when_every_holdout_outcome_is_flipped() -> None:
    games = _season_of_games()
    flipped = [
        replace(line_game, game=replace(
            line_game.game, home_score=line_game.game.away_score, away_score=(line_game.game.home_score or 0) + 21,
        )) if line_game.game.season in HOLDOUT_SEASONS else line_game
        for line_game in games
    ]

    assert fit(flipped) == fit(games)


def _score(market: float, blend_loss: float, **extra: object) -> NflArmScore:
    return NflArmScore("set", 1000, market, market, blend_loss, **extra)  # type: ignore[arg-type]


def test_moneyline_is_adopted_only_when_log_loss_and_brier_both_improve_and_no_bucket_gets_worse() -> None:
    better = _score(0.65, 0.64, market_brier=0.23, blend_brier=0.22)
    buckets_fine = [_score(0.66, 0.65), _score(0.64, 0.64)]

    assert adopted("moneyline", better, buckets_fine)
    assert not adopted("moneyline", replace(better, blend_brier=0.23), buckets_fine)
    assert not adopted("moneyline", better, [_score(0.66, 0.67), _score(0.64, 0.63)])
    # A zero blend weight reproduces the market exactly: a tie, so rejected.
    assert not adopted("moneyline", _score(0.65, 0.65, market_brier=0.23, blend_brier=0.23), buckets_fine)


@pytest.mark.parametrize(
    "blend_mae, record, expected",
    [
        (9.9, PickRecord(53, 47, 3), True),
        (9.9, PickRecord(52, 48, 0), False),  # 52.0% is under the 52.4% breakeven
        (9.9, PickRecord(52, 46, 0), False),  # 98 decided picks, under the minimum
        (10.0, PickRecord(80, 40, 0), False),  # no MAE improvement over the line
    ],
)
def test_spread_and_total_need_a_better_mae_and_enough_winning_picks(
    blend_mae: float, record: PickRecord, expected: bool,
) -> None:
    score = _score(10.0, blend_mae, blend_picks={1.5: record, 3.0: record})

    assert ADOPTION_MIN_PICKS == 100
    assert adopted("spread", score, []) is expected
    assert adopted("total", score, []) is expected
