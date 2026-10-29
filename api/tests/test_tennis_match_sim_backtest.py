from collections import defaultdict
from datetime import date

import numpy as np
import pytest

from app.backtest.tennis_match_sim import (
    CountSample, DispersionFit, LevelCase, LevelRow, ServeSide, SetGapRow, dispersion_report, fit_dispersion,
    holds_for_win_prob, leave_one_out, level_report, level_rows, match_level_cases, played_fantasy_score,
    serve_sides, set_gap_report, set_gap_rows,
)
from app.core.box_score_join import BoxScoreCandidate
from app.core.tennis_match_chain import SET_EFFECT_SD, mixed_match_distribution
from app.core.tennis_match_sim import simulate_match
from app.services.tennis.prop_sim import MatchSim


def test_holds_reproduce_the_win_prob_around_the_level():
    hold_a, hold_b = holds_for_win_prob(0.7, 0.78)

    assert (hold_a + hold_b) / 2 == pytest.approx(0.78)
    assert mixed_match_distribution(hold_a, hold_b, 3).win_prob == pytest.approx(0.7, abs=1e-6)


def test_rows_cover_each_level_and_win_prob():
    rows = set_gap_rows(0.0, levels=(0.8,), win_probs=(0.5, 0.8))

    assert [(row.level, row.win_prob) for row in rows] == [(0.8, 0.5), (0.8, 0.8)]
    assert rows[0].chain_three_sets == pytest.approx(0.5, abs=1e-9)


def test_the_frozen_effect_reproduces_the_set_fit():
    rows = set_gap_rows(SET_EFFECT_SD, levels=(0.75, 0.82), win_probs=(0.5, 0.8, 0.95))

    assert max(abs(row.gap) for row in rows) < 0.025


def _row(gap: float) -> SetGapRow:
    return SetGapRow(0.75, 0.6, 0.77, 0.73, 0.4 + gap, 0.4)


def test_report_without_effect_states_the_stop_rule_verdict():
    lines = set_gap_report([_row(0.05), _row(-0.01)]).splitlines()

    assert lines[0] == "Best-of-3 P(3 sets): exact chain (effect sd 0.000) vs tennis_sets fit"
    assert lines[2] == "    0.75   0.60   0.770   0.730   0.450   0.400  +0.050"
    assert lines[-1] == "  largest gap 0.050 against stop 0.02: set effect required"
    assert set_gap_report([_row(0.01)]).splitlines()[-1].endswith("chain used as is")


def test_report_with_effect_states_the_residual():
    assert set_gap_report([_row(-0.03)], 0.14).splitlines()[-1] == "  largest residual gap 0.030 with the effect"


_HEADER = "score,winner_name,loser_name,w_svpt,w_ace,w_df,l_svpt,l_ace,l_df\n"


def test_serve_sides_keep_completed_sides_with_serve_points():
    contents = _HEADER + (
        "6-4 6-4,A,B,60,5,2,55,3,4\n"
        "6-4 2-1 RET,A,C,30,2,1,20,1,0\n"
        "W/O,A,D,,,,,,\n"
        "6-3 6-2,A,E,50,4,1,0,0,0\n"
    )

    sides = serve_sides(contents, "ATP")

    assert sides == [
        ServeSide("ATP", "A", 60, 5, 2), ServeSide("ATP", "B", 55, 3, 4), ServeSide("ATP", "A", 50, 4, 1),
    ]


def test_leave_one_out_rates_exclude_the_scored_match_and_thin_players():
    sides = [ServeSide("ATP", "A", 50 + i, i, 1) for i in range(6)] + [ServeSide("ATP", "B", 60, 3, 2)]

    samples = leave_one_out(sides, "aces")

    assert len(samples) == 6
    first = samples[0]
    assert first.count == 0 and first.serve_points == 50
    assert first.rate == pytest.approx(sum(range(1, 6)) / sum(51 + i for i in range(5)))


def test_fit_recovers_a_known_gamma_shape():
    rng = np.random.default_rng(48)
    points = rng.integers(40, 120, size=40_000)
    rate = 0.08
    counts = rng.binomial(points, np.minimum(1.0, rate * rng.gamma(4.0, 0.25, size=points.size)))
    samples = [CountSample("ATP", int(n), rate, int(c)) for n, c in zip(points, counts)]

    fit = fit_dispersion("aces", samples)

    assert fit.shape == pytest.approx(4.0, rel=0.1)
    assert fit.ratio_before["all"] > 1.5
    assert fit.ratio_after["all"] == pytest.approx(1.0)


def test_fit_without_excess_has_no_shape():
    samples = [CountSample("WTA", 50, 0.1, 5)] * 10

    fit = fit_dispersion("double_faults", samples)

    assert fit.shape is None
    assert fit.ratio_after["WTA"] == fit.ratio_before["WTA"] == 0.0


def test_dispersion_report_lists_each_tour_then_all():
    fit = DispersionFit(
        "aces", 5.78, {"WTA": 4_349, "ATP": 4_671, "all": 9_020},
        {"ATP": 2.641, "WTA": 2.076, "all": 2.477}, {"ATP": 0.953, "WTA": 1.18, "all": 1.0},
    )

    lines = dispersion_report([fit]).splitlines()

    assert lines[2] == "  aces          ATP      4,671     2.641   0.953"
    assert lines[4] == "  aces          all      9,020     2.477   1.000"
    assert lines[5] == "  aces gamma shape 5.78"
    no_shape = DispersionFit("double_faults", None, {"all": 1}, {"all": 0.9}, {"all": 0.9})
    assert dispersion_report([no_shape]).splitlines()[-1] == "  double_faults gamma shape none (no excess)"


def _box(aces: int | None = 6, double_faults: int | None = 2, converted: int | None = 3) -> BoxScoreCandidate:
    return BoxScoreCandidate(1, date(2026, 5, 1), "W", "B", "6-4 6-3", aces, double_faults, converted)


def test_played_fantasy_score_follows_the_formula():
    # Games 12-7 (+5), sets 2-0 (+6), aces +3, DF -1.
    assert played_fantasy_score([(6, 4), (6, 3)], True, _box()) == pytest.approx(23.0)
    assert played_fantasy_score([(6, 4), (6, 3)], False, _box()) == pytest.approx(10 - 5 - 6 + 3 - 1)
    assert played_fantasy_score([(6, 4)], True, _box(aces=None)) is None


def _sim(players: tuple[int, int] = (3, 7)) -> MatchSim:
    draws = simulate_match(0.8, 0.75, 3, 0.07, 0.05, 0.03, 0.04, draws=2_000, seed=5)
    return MatchSim(players, draws, (0.8, 0.75), 0.6, "market", 21.5, 0.5, False, 5, frozenset(), frozenset())


def test_match_level_cases_orient_each_player_and_skip_missing_boxes():
    # p1 is the higher id, so it is the simulation's player B.
    cases = match_level_cases("WTA", "6-4 7-6", 7, _sim(), {7: _box(), 3: None})
    by_stat = defaultdict(list)
    for case in cases:
        by_stat[case.stat].append(case)

    assert [c.actual for c in by_stat["total_games"]] == [23.0]
    assert [c.actual for c in by_stat["total_tie_breaks"]] == [1.0]
    assert sorted(c.actual for c in by_stat["total_games_won"]) == [10.0, 13.0]
    assert [c.actual for c in by_stat["aces"]] == [6.0]
    assert [c.actual for c in by_stat["fantasy_score"]] == [pytest.approx(10 + 3 + 6 + 3 - 1)]
    total_model = by_stat["total_games"][0].model
    assert sum(c.model for c in by_stat["total_games_won"]) == pytest.approx(total_model)
    assert {c.tour for c in cases} == {"WTA"}


def test_level_rows_flag_a_bias_at_the_threshold():
    cases = [LevelCase("WTA", "total_sets", 2.0, 2.0), LevelCase("ATP", "aces", 6.0, 6.5),
             LevelCase("ATP", "aces", 4.0, 4.5), LevelCase("WTA", "aces", 3.0, 3.25)]

    atp_aces, wta_aces, sets = level_rows(cases)

    assert (atp_aces.tour, atp_aces.n, atp_aces.unverified) == ("ATP", 2, True)
    assert (wta_aces.tour, wta_aces.unverified) == ("WTA", False)
    assert (sets.stat, sets.unverified) == ("total_sets", False)


def test_level_report_lists_the_unverified_constant():
    rows = [LevelRow("total_games", "ATP", 830, 22.4, 22.1), LevelRow("aces", "WTA", 1_400, 2.9, 3.0)]

    lines = level_report(rows, 1_600, {"unfinished": 40, "not simulated": 0}).splitlines()

    assert lines[0] == "Level check: 1600 completed matches simulated from pre-start odds (skipped: 40 unfinished)"
    assert lines[2] == "  total_games               ATP       830    22.40    22.10   -0.30   0.25  unverified"
    assert lines[3] == "  aces                      WTA     1,400     2.90     3.00   +0.10   0.50  ok"
    assert lines[-1] == '  SIM_LEVEL_UNVERIFIED = frozenset({("total_games", "ATP")})'
