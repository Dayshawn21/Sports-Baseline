from dataclasses import replace

import numpy as np
import pytest

from app.core.tennis_match_sim import simulate_match
from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.routers.props import MarketTotal, enrich_with
from app.schemas.props import PropLine
from app.services.tennis import prop_sim
from app.services.tennis.prop_sim import SIM_STATS, SimInputs, line_probabilities, sim_prop_lines, stat_values
from tests.test_props_audit_projection import _prop, _stats

DRAWS = simulate_match(0.8, 0.74, 3, 0.07, 0.05, 0.035, 0.045, draws=4_000, seed=2)


@pytest.mark.parametrize("stat", sorted(SIM_STATS))
@pytest.mark.parametrize("player", [0, 1])
def test_every_stat_has_a_value_per_draw(stat: str, player: int) -> None:
    values = stat_values(DRAWS, stat, player)

    assert values is not None
    assert values.shape == (4_000,)
    probs = line_probabilities(values, float(np.median(values)) + 0.5)
    assert probs.p_over + probs.p_under + probs.p_push == pytest.approx(1.0)


def test_page_stat_names_are_normalized() -> None:
    assert np.array_equal(stat_values(DRAWS, "Total Games Won", 0), DRAWS.games_won[0])
    assert np.array_equal(stat_values(DRAWS, "1st Set Total Games", 1), DRAWS.first_set_games.sum(axis=0))


def test_an_integer_line_has_a_push_and_a_half_line_none() -> None:
    values = np.array([20, 21, 21, 22, 23])

    assert line_probabilities(values, 21.0).p_push == pytest.approx(0.4)
    assert line_probabilities(values, 21.0).p_over == pytest.approx(0.4)
    assert line_probabilities(values, 21.5).p_push == 0.0
    assert line_probabilities(values, 21.5).p_under == pytest.approx(0.6)


def test_both_players_games_make_the_match_total() -> None:
    a_games = stat_values(DRAWS, "total_games_won", 0)
    b_games = stat_values(DRAWS, "total_games_won", 1)

    assert np.array_equal(a_games + b_games, stat_values(DRAWS, "total_games", 0))
    assert np.array_equal(stat_values(DRAWS, "total_games", 0), stat_values(DRAWS, "total_games", 1))


def test_fantasy_score_follows_the_formula_on_one_draw() -> None:
    i = 17
    games, sets = DRAWS.games_won[:, i], DRAWS.sets_won[:, i]
    expected = (
        10 + games[1] - games[0] + 3 * (sets[1] - sets[0])
        + 0.5 * DRAWS.aces[1, i] - 0.5 * DRAWS.double_faults[1, i]
    )

    assert stat_values(DRAWS, "fantasy_score", 1)[i] == pytest.approx(expected)


def test_break_points_won_are_the_players_breaks() -> None:
    assert np.array_equal(stat_values(DRAWS, "break_points_won", 0), DRAWS.breaks[0])


def test_an_unsupported_stat_returns_none() -> None:
    assert stat_values(DRAWS, "moneyline", 0) is None


def _inputs(*, market: bool = True, ensemble: bool = True, total: MarketTotal | None = MarketTotal(22.5, -110, -110),
            p2_stats: PlayerRollingStats | None = None) -> SimInputs:
    stats = {(1, None): _stats(1, aces_per_game=0.08), (2, None): p2_stats or _stats(2, aces_per_game=0.06)}
    return SimInputs(
        opponent_ids={(1, 10): 2, (2, 10): 1},
        rolling_stats=stats,
        prediction_probs={(1, 10): 0.6, (2, 10): 0.4} if ensemble else {},
        market_probs={(1, 10): 0.64, (2, 10): 0.36} if market else {},
        market_totals={10: total} if total is not None else {},
    )


def _props(*stats: tuple[int, str, str]) -> list[Prop]:
    return [
        replace(_prop(line), id=i, player_id=player, stat_type=stat, best_of=3, player_tour="ATP")
        for i, (player, stat, line) in enumerate(stats)
    ]


def _rows(props: list[Prop], inputs: SimInputs) -> list[PropLine]:
    v3 = enrich_with(props, inputs.opponent_ids, inputs.rolling_stats, inputs.prediction_probs,
                     inputs.market_probs, inputs.market_totals)
    return sim_prop_lines(props, v3, inputs)


def test_both_players_read_one_simulation() -> None:
    props = _props((1, "Total Games Won", "11.5"), (2, "Total Games Won", "10.5"), (1, "Total Games", "22.5"))
    a_games, b_games, total = _rows(props, _inputs())

    assert a_games.stat_avg + b_games.stat_avg == pytest.approx(total.stat_avg, abs=0.02)
    assert a_games.projection_inputs["sim_seed"] == b_games.projection_inputs["sim_seed"]
    assert a_games.projection_inputs["sim_hold_player"] == b_games.projection_inputs["sim_hold_opponent"]


def test_the_book_total_and_moneyline_anchor_the_row() -> None:
    (row,) = _rows(_props((1, "Total Games", "22.5")), _inputs())

    assert row.projection_status == "ok"
    assert row.p_over == pytest.approx(0.5, abs=0.03)
    assert row.p_over + row.p_under + row.p_push == pytest.approx(1.0, abs=0.002)
    assert row.projection_inputs["sim_win_prob"] == pytest.approx(0.64)
    assert row.projection_inputs["sim_win_prob_source"] == "market"
    assert row.projection_inputs["sim_total_anchor"] == "book"
    assert row.projection_inputs["market_total_over_prob"] == pytest.approx(0.5)
    assert row.recommendation in ("OVER", "UNDER")
    assert row.confidence is None


def test_no_moneyline_falls_back_to_the_ensemble_with_a_flag() -> None:
    (row,) = _rows(_props((1, "Aces", "5.5")), _inputs(market=False))

    assert "no_market_moneyline" in row.data_quality_flags
    assert row.projection_inputs["sim_win_prob"] == pytest.approx(0.6)


def test_no_book_total_anchors_on_stats_and_keeps_the_flag() -> None:
    (row,) = _rows(_props((1, "Double Faults", "2.5")), _inputs(total=None))

    assert "no_market_total" in row.data_quality_flags
    assert row.projection_inputs["sim_total_anchor"] == "stats"
    assert "market_total_games" not in row.projection_inputs
    assert row.confidence is None


def test_no_win_probability_gets_no_projection() -> None:
    (row,) = _rows(_props((1, "Total Games", "22.5")), _inputs(market=False, ensemble=False))

    assert row.stat_avg is None and row.p_over is None and row.recommendation is None
    assert row.projection_status == "missing_prediction"
    assert row.projection_inputs == {}


def test_a_player_without_an_ace_rate_gets_no_aces_or_fantasy_score() -> None:
    no_aces = replace(_stats(2), aces_per_game=None)
    aces, fantasy, games = _rows(
        _props((2, "Aces", "4.5"), (2, "Fantasy Score", "18.5"), (2, "Total Games Won", "10.5")),
        _inputs(p2_stats=no_aces),
    )

    assert aces.stat_avg is None and fantasy.stat_avg is None
    assert aces.projection_status == "unsupported_stat"
    assert games.projection_status == "ok"


def test_over_only_payouts_play_the_over() -> None:
    (row,) = _rows([replace(p, odds_type="demon") for p in _props((1, "Aces", "9.5"))], _inputs())

    assert row.recommendation == "OVER"
    assert row.hit_probability == pytest.approx(row.p_over / (1 - row.p_push), abs=0.002)


def test_the_load_bearing_inputs_are_recorded() -> None:
    (row,) = _rows(_props((1, "Fantasy Score", "18.5")), _inputs())

    assert {
        "sim_hold_player", "sim_hold_opponent", "sim_win_prob", "sim_win_prob_source", "sim_total_anchor",
        "market_total_games", "market_total_over_prob", "sim_clamped", "sim_draws", "sim_seed", "sim_set_effect_sd",
    } <= set(row.projection_inputs)


def test_the_same_inputs_reproduce_the_row() -> None:
    props, inputs = _props((1, "Aces", "5.5")), _inputs()

    assert _rows(props, inputs) == _rows(props, inputs)


def test_a_stat_listed_unverified_carries_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prop_sim, "SIM_LEVEL_UNVERIFIED", frozenset({("aces", "ATP"), ("total_games_won", "ATP")}))
    aces, games_won, total = _rows(
        _props((1, "Aces", "5.5"), (1, "Games Won", "11.5"), (1, "Total Games", "22.5")), _inputs(),
    )

    assert "sim_level_unverified" in aces.data_quality_flags
    assert "sim_level_unverified" in games_won.data_quality_flags
    assert "sim_level_unverified" not in total.data_quality_flags
    assert aces.projection_status == "ok"


def test_level_names_fold_the_page_aliases() -> None:
    assert prop_sim.level_stat("Games Won") == "total_games_won"
    assert prop_sim.level_stat("Break Points Converted") == "break_points_won"
    assert prop_sim.level_stat("Aces") == "aces"


def test_rows_keep_their_order_when_matches_interleave() -> None:
    props = _props((1, "Aces", "5.5"), (1, "Total Games", "22.5"), (2, "Aces", "4.5"))
    props[1] = replace(props[1], match_id=11)
    inputs = replace(_inputs(), opponent_ids={(1, 10): 2, (2, 10): 1, (1, 11): 2})

    rows = _rows(props, inputs)

    assert [row.id for row in rows] == [0, 1, 2]
    assert rows[0].projection_inputs["sim_seed"] == rows[2].projection_inputs["sim_seed"]
    assert rows[1].projection_status != "ok"
