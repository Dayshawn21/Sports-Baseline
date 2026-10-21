import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.odds import odds_are_stale
from app.core.tennis_elo import TennisEloMatch, TennisEloRating
from app.ml.asof_features import HistoryIndex
from app.ml.elo_history import EloIndex
from app.repositories.matches import Match
from app.repositories.players import Player, PlayerElo
from app.repositories.tennis_elo import SOURCE, TennisEloSnapshot
from app.services.tennis import predictor
from app.services.tennis.elo_comparison import (
    ExperimentConfig, build_plan, runtime_pins, source_result_targets,
)
from app.services.tennis.ensemble import EnsembleInput, blend

NOW = datetime(2026, 10, 21, 13, 30, tzinfo=timezone.utc)
DAY = NOW.date()


class Registry:
    def __init__(self):
        self.calls = []

    def get_lgbm_version(self, tour):
        return "v6" if tour in {"ATP", "WTA"} else None

    def predict_lgbm(self, tour, features):
        self.calls.append((tour, dict(features)))
        return 0.57

    def serves_tour(self, tour):
        return tour in {"ATP", "WTA"}


def match():
    return Match(50, "future", DAY, NOW + timedelta(hours=2), "ATP", "Hard", "Tokyo", "R16",
                 3, 1, 2, 10, 20, None, "scheduled", None)


def batch():
    results = [(DAY - timedelta(days=i), 1, 2, 1 if i % 2 else 2, "Hard") for i in range(1, 21)]
    return predictor.PredictionBatch(
        {i: Player(i, f"Player {i}", f"player {i}", "ATP") for i in (1, 2)},
        {1: PlayerElo(1, DAY, 1600., 1580., None, None),
         2: PlayerElo(2, DAY, 1560., 1560., None, None)}, {}, {}, {}, {},
        {50: {"book": "draftkings", "p1_odds": -110, "p2_odds": -110, "line": None,
              "fetched_at": NOW - timedelta(minutes=5), "row_id": 100}}, {}, {},
        HistoryIndex(results), EloIndex(results),
    )


def candidates():
    return {i: TennisEloSnapshot(
        player_id=i, source=SOURCE, as_of_date=DAY,
        rating=TennisEloRating(1550. if i == 1 else 1500., 1520. if i == 1 else 1500., None, None, 30, 20, 0, 0),
        provider_namespace="ATP", provider_player_id=f"A{i}", computed_at=NOW - timedelta(hours=1),
        source_downloaded_at=NOW - timedelta(hours=2), replay_cutoff=DAY, method_version=SOURCE,
        manifest_sha256="a" * 64,
    ) for i in (1, 2)}


def config(registry=None, active=True):
    registry = registry or Registry()
    return ExperimentConfig.from_record({**runtime_pins(registry, "d" * 64),
                                         "activated_at": (NOW - timedelta(days=1)).isoformat() if active else None})


def plan(m=None, b=None, c=None, cfg=None, registry=None, **kwargs):
    return build_plan([m or match()], b or batch(), registry or Registry(),
                      candidates() if c is None else c, cfg or config(),
                      now=NOW, cycle_key=NOW.replace(minute=0), resulted=kwargs.pop("resulted", set()),
                      frozen=kwargs.pop("frozen", set()), **kwargs)


def test_baseline_matches_shared_predictor_and_candidate_changes_only_elo_input():
    reg, inputs = Registry(), batch()
    baseline = inputs.build(reg, match(), now=NOW)
    reg.calls.clear()
    result = plan(b=inputs, registry=reg)
    assert len(result.pairs) == 1 and result.preview_pairs == 1 and result.experiment_active
    pair = result.pairs[0]
    assert pair.incumbent.win_probability == baseline.p1_win_prob
    assert pair.incumbent.elo_probability == baseline.p1_elo_prob
    assert dict(pair.incumbent.weights) == baseline.ensemble_weights
    assert pair.market.row_id == 100 and pair.market.book == "draftkings"
    assert pair.market.p1_probability == baseline.p1_market_prob == .5
    assert pair.ml_probability == baseline.p1_ml_prob == .57
    assert len(reg.calls) == 1
    assert pair.candidate.elo_probability == pytest.approx(1 / (1 + 10 ** (-20 / 400)))
    expected = blend(EnsembleInput(tour="ATP", elo_prob=pair.candidate.elo_probability,
                                    ml_prob=.57, market_prob=.5, ml_features_partial=True))
    assert pair.candidate.win_probability == expected.p1_win_prob
    assert result.cycle.attempts[0].reason == "paired"


def test_surface_fallback_uses_both_overall_ratings_if_either_surface_is_missing():
    source = candidates()
    source[2] = replace(source[2], rating=replace(source[2].rating, hard=None, hard_matches=0))
    pair = plan(c=source).pairs[0]
    assert pair.candidate.elo_probability == pytest.approx(1 / (1 + 10 ** (-50 / 400)))


def test_candidate_gap_gate_is_retained_in_sample_as_market_only_forecast():
    source = candidates()
    source[1] = replace(source[1], rating=replace(source[1].rating, overall=2500., hard=2500.))
    value = plan(c=source).pairs[0]
    assert value.candidate.elo_unreliable is True and value.candidate.win_probability == .5
    assert value.candidate.weights == (("market", 1.),)
    assert "elo_unreliable" in value.candidate.quality_flags


def test_incumbent_gap_gate_does_not_remove_otherwise_eligible_match():
    inputs = batch()
    inputs.elo[1] = replace(inputs.elo[1], elo_hard=2500.)
    value = plan(b=inputs).pairs[0]
    assert value.incumbent.elo_unreliable and value.incumbent.win_probability == .5
    assert not value.candidate.elo_unreliable


def test_flipping_player_order_flips_both_forecasts_and_copies_rating_orientation():
    original = plan().pairs[0]
    flipped = plan(m=replace(match(), p1_id=2, p2_id=1)).pairs[0]
    assert flipped.incumbent.win_probability == pytest.approx(1 - original.incumbent.win_probability)
    assert flipped.candidate.win_probability == pytest.approx(1 - original.candidate.win_probability)
    assert [s.player_id for s in flipped.candidate_ratings] == [2, 1]


@pytest.mark.parametrize("change, reason", [
    ({"status": "live"}, "not_unstarted"), ({"winner_id": 1}, "not_unstarted"),
    ({"start_utc": NOW}, "already_started"), ({"start_utc": None}, "unknown_kickoff"),
    ({"start_utc": NOW.replace(tzinfo=None)}, "unknown_kickoff"),
    ({"p1_id": 2}, "ambiguous_players_or_group"), ({"p1_id": 99}, "ambiguous_players_or_group"),
    ({"round": "Q1"}, "qualifying"), ({"tournament": "Tokyo Qualifying"}, "qualifying"),
    ({"tournament": "ITF Tokyo"}, "outside_population"),
    ({"tournament": "Tokyo Exhibition"}, "outside_population"),
])
def test_unstarted_main_draw_eligibility(change, reason):
    result = plan(m=replace(match(), **change))
    assert result.pairs == () and result.cycle.attempts[0].reason == reason
    assert not result.cycle.attempts[0].incumbent_eligible


@pytest.mark.parametrize("change, reason", [
    ({"fetched_at": NOW - timedelta(hours=6, seconds=1)}, "stale_market"),
    ({"fetched_at": NOW + timedelta(seconds=1)}, "unavailable_market"),
    ({"fetched_at": None}, "unavailable_market"), ({"row_id": None}, "missing_market"),
    ({"p1_odds": None}, "missing_market"),
])
def test_unavailable_market_does_not_enter_coverage_denominator(change, reason):
    inputs = batch()
    inputs.odds[50].update(change)
    result = plan(b=inputs)
    assert result.pairs == () and result.cycle.attempts[0].reason == reason
    assert not result.cycle.attempts[0].incumbent_eligible


def test_exact_staleness_boundary_is_admitted():
    inputs = batch()
    inputs.odds[50]["fetched_at"] = NOW - timedelta(hours=6)
    assert len(plan(b=inputs).pairs) == 1


def test_missing_or_thin_candidates_remain_in_incumbent_denominator():
    source = candidates()
    source[1] = replace(source[1], rating=TennisEloRating(1500., None, None, None, 9, 0, 0, 0))
    for incoming in ({}, source):
        result = plan(c=incoming)
        assert not result.pairs and result.cycle.attempts[0].incumbent_eligible
        assert not result.cycle.attempts[0].candidate_available


def test_stored_result_and_previously_frozen_pair_are_skipped():
    assert plan(resulted={50}).cycle.attempts[0].reason == "not_unstarted"
    assert plan(frozen={50}).cycle.attempts[0].reason == "already_frozen"
    assert not plan(frozen={50}).pairs


def test_wta_125_and_unknown_namespaces_are_outside_sample():
    inputs = batch()
    inputs.players[1].tour = inputs.players[2].tour = "WTA"
    result = plan(m=replace(match(), tour="CHALLENGER"), b=inputs)
    assert not result.pairs and not result.cycle.attempts[0].incumbent_eligible


@pytest.mark.parametrize("tour, group, namespace", [("WTA", "WTA", "WTA"),
                                                   ("CHALLENGER", "ATP_CHALLENGER", "ATP")])
def test_groups_use_existing_fit_and_keep_provider_namespaces(tour, group, namespace):
    inputs, source = batch(), candidates()
    for player in inputs.players.values():
        player.tour = namespace
    for pid in source:
        source[pid] = replace(source[pid], provider_namespace=namespace)
    value = plan(m=replace(match(), tour=tour), b=inputs, c=source).pairs[0]
    assert value.group == group and value.candidate_ratings[0].provider_namespace == namespace


def test_inactive_and_not_yet_started_experiments_preview_without_storable_pairs():
    result = plan(cfg=config(active=False))
    assert result.preview_pairs == 1 and not result.pairs and not result.experiment_active
    cfg = replace(config(), activated_at=NOW)
    assert cfg.eligible_from == DAY + timedelta(days=1)
    result = plan(cfg=cfg)
    assert not result.pairs and result.cycle.attempts[0].reason == "before_experiment_start"
    result = plan(m=replace(match(), start_utc=NOW + timedelta(days=1)), cfg=cfg)
    assert result.preview_pairs == 1 and not result.pairs


def test_activation_start_is_utc_based_even_when_local_date_differs():
    cfg = replace(config(), activated_at=datetime(2026, 10, 20, 20, 30,
                                                tzinfo=timezone(timedelta(hours=-5))))
    assert cfg.eligible_from == date(2026, 10, 22)


def test_pinned_version_coefficient_gate_or_identity_changes_stop_runtime(monkeypatch):
    reg, cfg = Registry(), config()
    cfg.check_runtime(reg, "d" * 64)
    with pytest.raises(ValueError, match="changed"):
        cfg.check_runtime(reg, "f" * 64)
    monkeypatch.setattr(reg, "get_lgbm_version", lambda tour: "v7")
    with pytest.raises(ValueError, match="changed"):
        cfg.check_runtime(reg, "d" * 64)
    for field in ("coefficient_sha256", "gate_sha256"):
        with pytest.raises(ValueError, match="changed"):
            replace(cfg, **{field: "0" * 64}).check_runtime(Registry(), "d" * 64)


def test_provider_results_identify_target_even_if_local_status_has_not_updated():
    result = TennisEloMatch("ATP", "ATP", "2026-329", 1, DAY - timedelta(days=2), "R16", "A", "Hard",
                            "A1", "Player 1", "A2", "Player 2", "Tokyo", "6-4 6-4", 3)
    assert source_result_targets([match()], [result], candidates()) == {50}
    assert source_result_targets([match()], [replace(result, tournament="Paris")], candidates()) == set()
    assert source_result_targets([match()], [replace(result, round="R32")], candidates()) == set()


def test_single_match_serving_path_and_shared_batch_have_full_output_parity(monkeypatch):
    inputs, reg, m = batch(), Registry(), match()
    async def player(_db, pid): return inputs.players[pid]
    async def elo(_db, pid): return inputs.elo[pid]
    async def none(*args, **kwargs): return None
    async def h2h(*args, **kwargs): return {"p1_wins": 0, "p2_wins": 0}
    async def history(*args, **kwargs):
        return {"rest_days": None, "experience": 0., "matches_10d": 0., "matches_30d": 0., "streak": 0., "last_surface": None}
    async def odds(*args, **kwargs): return inputs.odds[m.id]
    async def indexes(*args): return inputs.history_index, inputs.elo_index
    monkeypatch.setattr(predictor.player_repo, "get_player_by_id", player)
    monkeypatch.setattr(predictor.player_repo, "get_latest_elo", elo)
    monkeypatch.setattr(predictor.player_repo, "get_rolling_stats", none)
    monkeypatch.setattr(predictor.player_repo, "get_contextual_rolling_stats", none)
    monkeypatch.setattr(predictor.match_repo, "get_h2h", h2h)
    monkeypatch.setattr(predictor.match_repo, "get_player_match_history", history)
    monkeypatch.setattr(predictor.match_repo, "get_latest_odds", odds)
    monkeypatch.setattr(predictor._history_cache, "get", indexes)
    monkeypatch.setattr(predictor, "odds_are_stale", lambda stamp, now=None: odds_are_stale(stamp, now=NOW))
    expected = asyncio.run(predictor.predict_match(None, reg, m))
    assert inputs.build(reg, m, now=NOW) == expected
