import pytest

from app.core.nfl_over_probability_calibration import CalibrationPair
from app.core.nfl_baseline import MIN_BASELINE_GAMES
from app.core.nfl_over_probability import over_probability, ratio_cdf
from app.core.nfl_season_blend import blend_averages
from app.core.nfl_volume_backtest import (
    K_RATE_GRID,
    K_SHARE_GRID,
    MAX_DISPERSION,
    SCORED_SEASONS,
    VOLUME_STATS,
    ReferenceDistribution,
    ScoredPair,
    VolumeHistory,
    VolumePlayerGame,
    VolumeTeamGame,
    _dispersion,
    best_k,
    build_cases,
    clustered_se,
    fit_reference,
    fit_volume,
    reference_distribution,
    reference_projection,
    score_origin,
    verdict,
)
from app.core.nfl_volume_projection import NO_FIT, project_player

QUANTILES = tuple(0.2 + 0.04 * i for i in range(41))


def _player(player_id: int, game_id: int, season: int, week: int, position: str = "WR", **stats: float | None):
    values = {stat: None for stat in VOLUME_STATS} | stats
    return VolumePlayerGame(player_id, game_id, season, week, position, team_id=1, is_home=True, stats=values,
                            target_share=None, offense_snaps=None)


def _team(game_id: int, season: int, week: int, total: float | None = 44.0, spread: float | None = 3.0,
          pass_attempts: float | None = 35.0):
    return VolumeTeamGame(game_id, 1, season, week, True, pass_attempts, 25.0, 60, spread, total)


def _season_history(seasons: dict[int, float], position: str = "WR", weeks: int = 6, players: int = 3) -> VolumeHistory:
    """Each season's games give every player `receptions` equal to that season's value."""
    player_games, team_games = [], []
    for season, receptions in seasons.items():
        for week in range(1, weeks + 1):
            game_id = season * 100 + week
            team_games.append(_team(game_id, season, week))
            for player in range(1, players + 1):
                player_games.append(_player(player, game_id, season, week, position,
                                            targets=receptions + player, receptions=receptions + player,
                                            receiving_yards=10.0 * (receptions + player)))
    return VolumeHistory(player_games, team_games)


def test_cases_carry_only_earlier_games_and_the_markets_the_position_is_priced_on() -> None:
    history = VolumeHistory(
        [
            _player(7, 1, 2023, 16, targets=5, receptions=3, receiving_yards=40),
            _player(7, 2, 2024, 1, targets=8, receptions=6, receiving_yards=70, rushing_yards=4),
            _player(7, 3, 2024, 2, targets=2, receptions=None, receiving_yards=12),
        ],
        [_team(1, 2023, 16), _team(2, 2024, 1), _team(3, 2024, 2)],
    )

    cases = {case.game_id: case for case in build_cases(history)}

    assert [(g.season, g.week) for g in cases[3].history] == [(2023, 16), (2024, 1)]
    assert cases[1].history == ()
    assert set(cases[2].actuals) == {"receptions", "receiving_yards"}
    assert cases[3].actuals == {"receiving_yards": 12.0}
    assert cases[3].history[1].team_pass_attempts == 35.0


def test_a_game_without_closing_lines_is_not_a_case_but_still_counts_as_history() -> None:
    history = VolumeHistory(
        [_player(7, 1, 2024, 1, targets=5, receptions=3), _player(7, 2, 2024, 2, targets=6, receptions=4)],
        [_team(1, 2024, 1, total=None), _team(2, 2024, 2)],
    )

    cases = build_cases(history)

    assert [case.game_id for case in cases] == [2]
    assert len(cases[0].history) == 1


def test_a_game_without_team_attempts_is_neither_a_case_nor_history() -> None:
    history = VolumeHistory(
        [_player(7, 1, 2024, 1, receptions=3), _player(7, 2, 2024, 2, receptions=4)],
        [_team(1, 2024, 1, pass_attempts=None), _team(2, 2024, 2)],
    )

    cases = build_cases(history)

    assert [case.game_id for case in cases] == [2]
    assert cases[0].history == ()


def test_the_reference_projection_is_v4s_blend_then_regression() -> None:
    history = VolumeHistory(
        [_player(7, 1, 2023, 10, receptions=2), _player(7, 2, 2023, 11, receptions=4),
         _player(7, 3, 2024, 1, receptions=7), _player(7, 4, 2024, 2, receptions=1)],
        [_team(game, season, week) for game, season, week in ((1, 2023, 10), (2, 2023, 11), (3, 2024, 1), (4, 2024, 2))],
    )
    case = [case for case in build_cases(history) if case.game_id == 4][0]
    blank = {stat: 0.0 for stat in ("passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
                                     "rushing_attempts", "receiving_yards", "touchdowns")} | {"fantasy_points": None}
    blended = blend_averages(blank | {"receptions": 7.0, "games": 1}, blank | {"receptions": 3.0, "games": 2})

    weight = min(1.0, blended["games"] / MIN_BASELINE_GAMES)
    expected = blended["receptions"] * weight + 5.0 * (1 - weight)
    assert reference_projection(case, "receptions", position_average=5.0) == pytest.approx(expected)


def test_the_reference_projection_needs_some_history() -> None:
    case = build_cases(VolumeHistory([_player(7, 1, 2024, 1, receptions=3)], [_team(1, 2024, 1)]))[0]

    assert reference_projection(case, "receptions", 5.0) is None


def test_ratio_cdf_reads_integer_thresholds_and_agrees_with_over_probability() -> None:
    assert 1.0 - ratio_cdf(QUANTILES, 10.0, 8.5) == pytest.approx(over_probability(QUANTILES, 10.0, 8.5).p_over)
    assert 0.0 < ratio_cdf(QUANTILES, 10.0, 8.0) < ratio_cdf(QUANTILES, 10.0, 9.0) < 1.0
    with pytest.raises(ValueError):
        ratio_cdf(QUANTILES, 0.0, 3.0)


def test_the_reference_fit_never_sees_a_season_after_the_fit_seasons() -> None:
    clean = build_cases(_season_history({2019: 2.0, 2020: 3.0, 2021: 4.0}))
    poisoned = build_cases(_season_history({2019: 2.0, 2020: 3.0, 2021: 4.0, 2022: 40.0, 2023: 90.0}))

    assert fit_reference(poisoned, [2020, 2021]) == fit_reference(clean, [2020, 2021])


def test_an_earlier_season_enters_only_as_pre_game_history_never_as_fit_outcomes() -> None:
    # 2019's games are what a 2020 case knew at kickoff, as in v4, so they move
    # the projections; 2019's own results are not fit cases.
    cases = build_cases(_season_history({2019: 2.0, 2020: 3.0}))

    fit = fit_reference(cases, [2020])

    assert fit.position_average[("receptions", "WR")] == pytest.approx(5.0)


def test_a_group_with_fewer_than_two_cases_gets_no_reference_fit() -> None:
    cases = build_cases(_season_history({2024: 3.0}, position="TE", weeks=2, players=1))

    fit = fit_reference(cases, [2024])

    assert ("receptions", "TE") not in fit.quantiles
    assert reference_distribution(cases[-1], "receptions", fit) is None


def test_the_reference_count_crps_reads_the_ratio_cdf_at_each_whole_number() -> None:
    forecast = ReferenceDistribution(QUANTILES, projection=5.0, is_count=True)
    by_hand = sum((forecast.cdf(k) - (1.0 if k >= 3 else 0.0)) ** 2 for k in range(0, 20))

    assert forecast.crps(3) == pytest.approx(by_hand)


def _lined_history(seasons: tuple[int, ...], players: dict[int, str], weeks: int = 8, identical: bool = False,
                   poison: float = 0.0) -> VolumeHistory:
    """Team attempts follow a known line: pass = 10 + 0.5 x team total - 0.3 x margin."""
    player_games, team_games = [], []
    for season in seasons:
        for week in range(1, weeks + 1):
            game_id = season * 100 + week
            total, spread = 38.0 + 2.0 * (week % 5), 3.0 * ((week % 3) - 1) + 0.5 * (week % 2)
            team_total = (total + spread) / 2
            pass_attempts = 40.0 if identical else 10.0 + 0.5 * team_total - 0.3 * spread + poison
            rush_attempts = 25.0 if identical else 20.0 + 0.1 * team_total + 0.4 * spread + poison
            team_games.append(VolumeTeamGame(game_id, 1, season, week, True, pass_attempts, rush_attempts, 60,
                                             spread, total))
            for player_id, position in players.items():
                targets = 5.0 if identical else float((week * player_id) % 7 + 2) + poison
                carries = 12.0 if identical else float((week + player_id) % 9 + 6)
                stats = dict(targets=targets, receptions=targets - 2, receiving_yards=8.0 * (targets - 2) + (0 if identical else week % 4),
                             rushing_attempts=carries, rushing_yards=4.0 * carries + (0 if identical else week % 3),
                             passing_attempts=float(round(pass_attempts)), passing_completions=float(round(pass_attempts * 0.6)),
                             passing_yards=pass_attempts * 7.0 + (0 if identical else week))
                player_games.append(_player(player_id, game_id, season, week, position, **stats))
    return VolumeHistory(player_games, team_games)


PLAYERS = {1: "WR", 2: "WR", 3: "WR", 4: "RB", 5: "RB", 6: "TE", 7: "TE", 8: "QB", 9: "QB"}


def test_the_team_volume_regression_recovers_a_known_line() -> None:
    fit = fit_volume(build_cases(_lined_history((2020, 2021), PLAYERS)), [2020, 2021])

    assert fit.params.pass_volume.intercept == pytest.approx(10.0)
    assert fit.params.pass_volume.total_slope == pytest.approx(0.5)
    assert fit.params.pass_volume.margin_slope == pytest.approx(-0.3)
    assert fit.params.rush_volume.margin_slope == pytest.approx(0.4)


def test_the_volume_fit_never_sees_a_season_after_the_fit_seasons() -> None:
    clean = build_cases(_lined_history((2020, 2021), PLAYERS))
    poisoned = clean + build_cases(_lined_history((2022,), PLAYERS, poison=25.0))

    assert fit_volume(poisoned, [2020, 2021]) == fit_volume(clean, [2020, 2021])


def test_grid_ties_resolve_to_the_smaller_k() -> None:
    assert best_k({2.0: 1.0, 4.0: 1.0, 8.0: 1.0}) == 2.0
    assert best_k({2.0: 1.0, 4.0: 1.0 - 1e-12, 8.0: 1.0}) == 2.0
    assert best_k({2.0: 1.0, 4.0: 0.5, 8.0: 0.5}) == 4.0

    # Identical players every game: every K gives the same forecasts.
    fit = fit_volume(build_cases(_lined_history((2021,), PLAYERS, identical=True)), [2021])
    assert fit.params.k_share == K_SHARE_GRID[0]
    assert set(fit.params.k_rate.values()) == {K_RATE_GRID[0]}


def test_a_group_with_fewer_than_two_cases_gets_no_fit_and_leaves_the_cohort() -> None:
    history = _lined_history((2021,), {1: "WR", 2: "WR", 3: "WR"}, weeks=6)
    lone_te = _lined_history((2021,), {9: "TE"}, weeks=2)
    cases = build_cases(VolumeHistory(history.player_games + lone_te.player_games, history.team_games))

    fit = fit_volume(cases, [2021])

    assert ("receptions", "TE") not in fit.params.dispersion
    te_case = [case for case in cases if case.position == "TE" and case.history][0]
    projection = project_player("TE", te_case.history, te_case.game, fit.params)
    assert projection.distributions == {} and set(projection.skipped.values()) == {NO_FIT}


def test_counts_no_more_spread_than_poisson_get_the_capped_dispersion() -> None:
    assert _dispersion([(3.0, 3.0), (4.0, 4.0), (5.0, 5.0)]) == MAX_DISPERSION
    over = [(0.0, 4.0), (9.0, 4.0), (1.0, 4.0), (8.0, 4.0)]
    excess = sum((y - m) ** 2 - m for y, m in over)
    assert _dispersion(over) == pytest.approx(4 * 16.0 / excess)


def _scored(season: int, i: int, difference: float, *, predicted: float = 0.3, over: bool | None = None,
            below: float | None = None, market: str = "receptions") -> ScoredPair:
    # Two pairs per game, so clustering by game matters; within every 10 pairs
    # exactly 30% go over at a predicted 0.3, so calibration is perfect.
    over = (i % 10) < 3 if over is None else over
    below = (1.0 if i % 2 == 0 else 0.0) if below is None else below
    return ScoredPair(i, season * 10_000 + i // 2, market, "WR", season, 10.0 + difference, 10.0,
                      (CalibrationPair(predicted, over),), below)


def _passing(per_season: int = 320, differences: dict[int, float] | None = None, noise: float = 0.1) -> list[ScoredPair]:
    pairs = []
    for season in SCORED_SEASONS:
        base = (differences or {}).get(season, -0.5)
        for i in range(per_season):
            sign = 1.0 if (i // 2) % 2 == 0 else -1.0
            pairs.append(_scored(season, i, base + sign * noise))
    return pairs


def test_clustered_se_treats_a_game_as_one_draw() -> None:
    independent = clustered_se([1.0, -1.0, 1.0, -1.0], [1, 2, 3, 4])
    assert independent == pytest.approx((4.0 / 16 * 4 / 3) ** 0.5)
    # The same values with each game's pairs moving together: the SE doubles.
    clustered = clustered_se([1.0, 1.0, -1.0, -1.0], [1, 1, 2, 2])
    assert clustered == pytest.approx((8.0 / 16 * 2 / 1) ** 0.5)
    with pytest.raises(ValueError):
        clustered_se([1.0, 2.0], [1, 1])


def test_a_market_meeting_every_clause_adopts() -> None:
    result = verdict("receptions", _passing())

    assert result.verdict == "adopt" and result.failed == ()
    assert result.seasons_won == 5 and result.share_below == pytest.approx(0.5)
    assert result.ece == pytest.approx(0.0)


def test_too_few_cases_in_any_season_is_insufficient() -> None:
    pairs = [pair for pair in _passing() if not (pair.season == 2023 and pair.player_id >= 299)]

    result = verdict("receptions", pairs)

    assert result.verdict == "insufficient" and result.failed == ("cases",)
    assert result.cases_by_season[2023] == 299


def test_a_lower_crps_within_two_standard_errors_fails_only_the_crps_clause() -> None:
    result = verdict("receptions", _passing(differences={s: -0.001 for s in SCORED_SEASONS}, noise=1.0))

    assert result.seasons_won == 5
    assert result.failed == ("crps",) and result.verdict == "reject"


def test_winning_only_three_seasons_fails_only_the_seasons_clause() -> None:
    result = verdict("receptions", _passing(differences={2021: -1.0, 2022: -1.0, 2023: -1.0, 2024: 0.2, 2025: 0.2}))

    assert result.seasons_won == 3
    assert result.failed == ("seasons",)


def test_miscalibrated_p_over_fails_only_the_calibration_clause() -> None:
    pairs = [
        _scored(pair.season, pair.player_id, pair.difference, predicted=0.5, over=(pair.player_id % 10) < 6)
        for pair in _passing()
    ]

    result = verdict("receptions", pairs)

    assert result.ece == pytest.approx(0.1)
    assert result.failed == ("calibration",)


def test_a_median_that_runs_high_fails_only_the_median_clause() -> None:
    pairs = [
        _scored(pair.season, pair.player_id, pair.difference, below=1.0 if pair.player_id % 10 < 6 else 0.0)
        for pair in _passing()
    ]

    result = verdict("receptions", pairs)

    assert result.share_below == pytest.approx(0.6)
    assert result.failed == ("median",)


def test_a_verdict_reads_only_its_own_market() -> None:
    noise = [_scored(2021, i, 5.0, market="receiving_yards") for i in range(400)]

    assert verdict("receptions", _passing() + noise).verdict == "adopt"


def test_scoring_an_origin_pairs_both_arms_on_their_common_cohort() -> None:
    history = _lined_history((2018, 2019), PLAYERS)
    rookie = _lined_history((2019,), {20: "WR"}, weeks=1)
    cases = build_cases(VolumeHistory(history.player_games + rookie.player_games, history.team_games))

    origin = score_origin(cases, 2019)

    keys = [pair.key for pair in origin.pairs]
    assert len(keys) == len(set(keys))
    scored = [(case, market) for case in cases if case.season == 2019 for market in case.actuals]
    assert len(origin.pairs) + sum(origin.excluded.values()) == len(scored)
    assert (20, 201901, "receptions") not in set(keys)
    assert origin.excluded[("receptions", "no volume forecast")] >= 1
    assert all(pair.season == 2019 and pair.over_pairs for pair in origin.pairs)


def test_an_origin_with_no_cases_in_its_season_raises() -> None:
    cases = build_cases(_lined_history((2018, 2019), PLAYERS))

    with pytest.raises(ValueError, match="no cases in season 2020"):
        score_origin(cases, 2020)
