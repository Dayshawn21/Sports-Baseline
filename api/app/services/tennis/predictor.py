"""
Main prediction orchestrator.
Fetches all data from DB, builds features, runs models, blends ensemble.
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.odds import american_to_prob, devig_two_way, odds_are_stale
from app.core.tennis_format import display_tour, infer_best_of
from app.ml.asof_features import HistoryIndex
from app.ml.elo_history import EloIndex
from app.ml.registry import ModelRegistry
from app.repositories import matches as match_repo
from app.repositories import players as player_repo
from app.repositories.matches import Match
from app.repositories.players import Player, PlayerElo, PlayerRollingStats
from app.services.tennis.ensemble import EnsembleInput, EnsembleResult, blend, elo_is_unreliable
from app.services.tennis.feature_builder import build_features
from app.services.tennis.history_cache import HistoryCache, asof_features, min_prior_matches


@dataclass
class PredictionOutput:
    match_id: int
    start_utc: Optional[datetime]
    p1_name: str
    p2_name: str
    tour: str
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    p1_win_prob: Optional[float]
    p2_win_prob: Optional[float]
    p1_elo_prob: Optional[float]
    p1_ml_prob: Optional[float]
    p1_market_prob: Optional[float]
    ensemble_weights: dict
    quality_flags: list[str]
    p1_odds_american: Optional[int]
    p2_odds_american: Optional[int]
    h2h_p1_wins: int
    h2h_p2_wins: int
    # Display label for `tour`. Separate because WTA 125 arrives labelled
    # CHALLENGER and only the players say which it is — see display_tour().
    tour_label: str = ""
    # Derived set-score picks assume best-of-3 math, so they need the format.
    # Defaulted (and therefore last) because best-of-3 is right for everything
    # except ATP slam main draws.
    best_of: int = 3
    # The exact feature vector this prediction was made from. Persisted to
    # predictions.feature_snapshot so a settled match can be graded against the inputs
    # as they stood at prediction time rather than as they look after later ingest.
    feature_snapshot: Optional[dict[str, float]] = None
    # Lets the slate link each name to the player page (32c).
    p1_id: Optional[int] = None
    p2_id: Optional[int] = None


logger = logging.getLogger(__name__)

# One cache for the process. Rebuilds itself when new results land.
_history_cache = HistoryCache()


def _snapshot(feat: dict) -> dict[str, float]:
    """JSON-safe copy of the feature vector for persistence.

    Anything that will not survive json.dumps is dropped rather than raised, because a
    single odd value must not take down the whole nightly prediction run.
    """
    out: dict[str, float] = {}
    for k, v in feat.items():
        if v is None or isinstance(v, bool):
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out[k] = f
    return out


def _elo_probability(feat: dict) -> float:
    """P(p1 wins) from the ELO gap, preferring the surface rating when both have one.

    build_features seeds d_surface_elo with a neutral default for model inputs, so
    has_surface_elo is the signal that the surface-specific value is real.
    """
    diff = (
        feat.get("d_surface_elo")
        if feat.get("has_surface_elo")
        else feat.get("d_elo", 0.0)
    )
    return 1.0 / (1.0 + 10 ** (-(diff or 0.0) / 400.0))


async def predict_match(
    db: AsyncSession,
    registry: ModelRegistry,
    match: Match,
) -> PredictionOutput:
    # ── Load player data ──────────────────────────────────────────────────────
    p1 = await player_repo.get_player_by_id(db, match.p1_id)
    p2 = await player_repo.get_player_by_id(db, match.p2_id)

    # ── ELO ───────────────────────────────────────────────────────────────────
    p1_elo = await player_repo.get_latest_elo(db, match.p1_id)
    p2_elo = await player_repo.get_latest_elo(db, match.p2_id)

    # ── Rolling stats ─────────────────────────────────────────────────────────
    surf = match.surface
    p1_stats = await player_repo.get_rolling_stats(db, match.p1_id, None, "last_52w")
    p2_stats = await player_repo.get_rolling_stats(db, match.p2_id, None, "last_52w")
    p1_surf = await player_repo.get_rolling_stats(db, match.p1_id, surf, "last_52w")
    p2_surf = await player_repo.get_rolling_stats(db, match.p2_id, surf, "last_52w")
    p1_last90 = await player_repo.get_contextual_rolling_stats(db, match.p1_id, None, "last90d", "overall", "all")
    p2_last90 = await player_repo.get_contextual_rolling_stats(db, match.p2_id, None, "last90d", "overall", "all")
    p1_top20 = await player_repo.get_contextual_rolling_stats(db, match.p1_id, None, "last_52w", "opp_rank", "top20")
    p2_top20 = await player_repo.get_contextual_rolling_stats(db, match.p2_id, None, "last_52w", "opp_rank", "top20")
    p1_top50 = await player_repo.get_contextual_rolling_stats(db, match.p1_id, None, "last_52w", "opp_rank", "top50")
    p2_top50 = await player_repo.get_contextual_rolling_stats(db, match.p2_id, None, "last_52w", "opp_rank", "top50")

    # ── H2H ───────────────────────────────────────────────────────────────────
    h2h_all = await match_repo.get_h2h(db, match.p1_id, match.p2_id, None)
    h2h_surf = await match_repo.get_h2h(db, match.p1_id, match.p2_id, surf)

    # ── Odds ──────────────────────────────────────────────────────────────────
    odds = await match_repo.get_latest_odds(db, match.id, "moneyline")
    p1_odds = odds["p1_odds"] if odds else None
    p2_odds = odds["p2_odds"] if odds else None
    odds_stale = odds_are_stale(odds.get("fetched_at") if odds else None)

    # ── Match history (rest days, experience, streak, recent activity) ──────
    ref_date = match.match_date or date.today()
    p1_history = await match_repo.get_player_match_history(db, match.p1_id, ref_date)
    p2_history = await match_repo.get_player_match_history(db, match.p2_id, ref_date)

    history_index, elo_index = await _history_cache.get(db)

    # ── Build feature vector ──────────────────────────────────────────────────
    feat, feat_flags = build_features(
        match=match, p1=p1, p2=p2,
        p1_elo=p1_elo, p2_elo=p2_elo,
        p1_stats=p1_stats, p2_stats=p2_stats,
        p1_surf_stats=p1_surf, p2_surf_stats=p2_surf,
        p1_last90_stats=p1_last90, p2_last90_stats=p2_last90,
        p1_top20_stats=p1_top20, p2_top20_stats=p2_top20,
        p1_top50_stats=p1_top50, p2_top50_stats=p2_top50,
        h2h_p1_wins=h2h_all["p1_wins"], h2h_p2_wins=h2h_all["p2_wins"],
        h2h_surf_p1_wins=h2h_surf["p1_wins"], h2h_surf_p2_wins=h2h_surf["p2_wins"],
        p1_odds_american=p1_odds, p2_odds_american=p2_odds,
        odds_stale=odds_stale,
        p1_history=p1_history, p2_history=p2_history,
        asof=asof_features(history_index, elo_index, match),
    )

    # ── ML inference ─────────────────────────────────────────────────────────
    ml_prob = registry.predict_lgbm(match.tour, feat)
    if not registry.serves_tour(match.tour):
        feat_flags.append("ml_not_trained_for_tour")

    # ── ELO probability (simple logistic from ELO diff) ───────────────────────
    elo_prob: Optional[float] = None
    if p1_elo and p2_elo and p1_elo.elo and p2_elo.elo:
        elo_prob = _elo_probability(feat)

    # ── Market no-vig ─────────────────────────────────────────────────────────
    market_prob: Optional[float] = None
    if p1_odds and p2_odds:
        market_prob, _ = devig_two_way(american_to_prob(p1_odds), american_to_prob(p2_odds))

    # ── Ensemble blend ────────────────────────────────────────────────────────
    prior_matches = min_prior_matches(history_index, match)
    result: Optional[EnsembleResult] = blend(
        EnsembleInput(
            tour=match.tour,
            elo_prob=elo_prob,
            ml_prob=ml_prob,
            market_prob=market_prob,
            elo_fallback="elo_missing" in feat_flags,
            ml_features_partial="ml_features_partial" in feat_flags,
            market_stale="stale_odds" in feat_flags,
            market_high_overround="high_overround" in feat_flags,
            elo_unreliable=elo_is_unreliable(elo_prob, market_prob, prior_matches),
        )
    )

    all_flags = list(set(feat_flags + (result.quality_flags if result else ["no_predictors"])))

    return PredictionOutput(
        match_id=match.id,
        start_utc=match.start_utc,
        p1_name=p1.name,
        p2_name=p2.name,
        tour=match.tour,
        tour_label=display_tour(match.tour, p1.tour if p1 else None, p2.tour if p2 else None),
        surface=match.surface,
        tournament=match.tournament,
        round=match.round,
        p1_win_prob=result.p1_win_prob if result else None,
        p2_win_prob=result.p2_win_prob if result else None,
        p1_elo_prob=elo_prob,
        p1_ml_prob=ml_prob,
        p1_market_prob=market_prob,
        ensemble_weights=result.weights if result else {},
        quality_flags=sorted(all_flags),
        p1_odds_american=p1_odds,
        p2_odds_american=p2_odds,
        h2h_p1_wins=h2h_all["p1_wins"],
        h2h_p2_wins=h2h_all["p2_wins"],
        best_of=infer_best_of(match.tour, match.tournament, match.round, match.best_of),
        feature_snapshot=_snapshot(feat),
        p1_id=match.p1_id,
        p2_id=match.p2_id,
    )


def _build_prediction(
    registry: ModelRegistry,
    match: Match,
    players: dict[int, Player],
    elo: dict[int, PlayerElo],
    stats: dict[tuple, PlayerRollingStats],
    ctx_last90: dict[tuple, PlayerRollingStats],
    ctx_top20: dict[tuple, PlayerRollingStats],
    ctx_top50: dict[tuple, PlayerRollingStats],
    odds: dict[int, dict],
    h2h: dict[tuple, dict],
    history: dict[int, dict],
    asof: Optional[dict] = None,
    prior_matches: Optional[int] = None,
    now: datetime | None = None,
) -> PredictionOutput:
    """Build a PredictionOutput from pre-fetched cache dicts (no DB calls)."""
    p1 = players.get(match.p1_id)
    p2 = players.get(match.p2_id)
    p1_elo = elo.get(match.p1_id)
    p2_elo = elo.get(match.p2_id)

    surf = match.surface
    p1_stats = stats.get((match.p1_id, None))
    p2_stats = stats.get((match.p2_id, None))
    p1_surf = stats.get((match.p1_id, surf)) if surf else None
    p2_surf = stats.get((match.p2_id, surf)) if surf else None
    p1_last90 = ctx_last90.get((match.p1_id, None, "all"))
    p2_last90 = ctx_last90.get((match.p2_id, None, "all"))
    p1_top20 = ctx_top20.get((match.p1_id, None, "top20"))
    p2_top20 = ctx_top20.get((match.p2_id, None, "top20"))
    p1_top50 = ctx_top50.get((match.p1_id, None, "top50"))
    p2_top50 = ctx_top50.get((match.p2_id, None, "top50"))

    _empty_h2h = {"p1_wins": 0, "p2_wins": 0}
    h2h_all = h2h.get((match.p1_id, match.p2_id, None), _empty_h2h)
    h2h_surf = h2h.get((match.p1_id, match.p2_id, surf), _empty_h2h) if surf else _empty_h2h

    match_odds = odds.get(match.id)
    p1_odds = match_odds["p1_odds"] if match_odds else None
    p2_odds = match_odds["p2_odds"] if match_odds else None
    odds_stale = odds_are_stale(match_odds.get("fetched_at") if match_odds else None, now=now)

    _empty_history = {"rest_days": None, "experience": 0.0, "matches_10d": 0.0, "matches_30d": 0.0, "streak": 0.0, "last_surface": None}
    p1_history = history.get(match.p1_id, _empty_history)
    p2_history = history.get(match.p2_id, _empty_history)

    feat, feat_flags = build_features(
        match=match, p1=p1, p2=p2,
        p1_elo=p1_elo, p2_elo=p2_elo,
        p1_stats=p1_stats, p2_stats=p2_stats,
        p1_surf_stats=p1_surf, p2_surf_stats=p2_surf,
        p1_last90_stats=p1_last90, p2_last90_stats=p2_last90,
        p1_top20_stats=p1_top20, p2_top20_stats=p2_top20,
        p1_top50_stats=p1_top50, p2_top50_stats=p2_top50,
        h2h_p1_wins=h2h_all["p1_wins"], h2h_p2_wins=h2h_all["p2_wins"],
        h2h_surf_p1_wins=h2h_surf["p1_wins"], h2h_surf_p2_wins=h2h_surf["p2_wins"],
        p1_odds_american=p1_odds, p2_odds_american=p2_odds,
        odds_stale=odds_stale,
        p1_history=p1_history, p2_history=p2_history,
        asof=asof,
    )

    ml_prob = registry.predict_lgbm(match.tour, feat)
    if not registry.serves_tour(match.tour):
        feat_flags.append("ml_not_trained_for_tour")

    elo_prob: Optional[float] = None
    if p1_elo and p2_elo and p1_elo.elo and p2_elo.elo:
        elo_prob = _elo_probability(feat)

    market_prob: Optional[float] = None
    if p1_odds and p2_odds:
        market_prob, _ = devig_two_way(american_to_prob(p1_odds), american_to_prob(p2_odds))

    result: Optional[EnsembleResult] = blend(
        EnsembleInput(
            tour=match.tour,
            elo_prob=elo_prob,
            ml_prob=ml_prob,
            market_prob=market_prob,
            elo_fallback="elo_missing" in feat_flags,
            ml_features_partial="ml_features_partial" in feat_flags,
            market_stale="stale_odds" in feat_flags,
            market_high_overround="high_overround" in feat_flags,
            elo_unreliable=elo_is_unreliable(elo_prob, market_prob, prior_matches),
        )
    )

    all_flags = list(set(feat_flags + (result.quality_flags if result else ["no_predictors"])))

    return PredictionOutput(
        match_id=match.id,
        start_utc=match.start_utc,
        p1_name=p1.name if p1 else "Unknown",
        p2_name=p2.name if p2 else "Unknown",
        tour=match.tour,
        tour_label=display_tour(match.tour, p1.tour if p1 else None, p2.tour if p2 else None),
        surface=match.surface,
        tournament=match.tournament,
        round=match.round,
        p1_win_prob=result.p1_win_prob if result else None,
        p2_win_prob=result.p2_win_prob if result else None,
        p1_elo_prob=elo_prob,
        p1_ml_prob=ml_prob,
        p1_market_prob=market_prob,
        ensemble_weights=result.weights if result else {},
        quality_flags=sorted(all_flags),
        p1_odds_american=p1_odds,
        p2_odds_american=p2_odds,
        h2h_p1_wins=h2h_all["p1_wins"],
        h2h_p2_wins=h2h_all["p2_wins"],
        best_of=infer_best_of(match.tour, match.tournament, match.round, match.best_of),
        feature_snapshot=_snapshot(feat),
        p1_id=match.p1_id,
        p2_id=match.p2_id,
    )


async def predict_today(
    db: AsyncSession,
    registry: ModelRegistry,
    match_date: date | list[date],
) -> list[PredictionOutput]:
    """Run predictions for all scheduled/live matches on a given date."""
    today_matches = await match_repo.get_upcoming(db, match_date)
    if not today_matches:
        return []
    ref_date = min(match_date) if isinstance(match_date, list) else match_date
    return await predict_matches(db, registry, today_matches, ref_date)


@dataclass
class PredictionBatch:
    players: dict[int, Player]
    elo: dict[int, PlayerElo]
    stats: dict[tuple[int, str | None], PlayerRollingStats]
    ctx_last90: dict[tuple[int, str | None, str], PlayerRollingStats]
    ctx_top20: dict[tuple[int, str | None, str], PlayerRollingStats]
    ctx_top50: dict[tuple[int, str | None, str], PlayerRollingStats]
    odds: dict[int, match_repo.MatchOdds]
    h2h: dict[tuple[int, int, str | None], dict[str, int]]
    history: dict[int, dict[str, float | str | None]]
    history_index: HistoryIndex
    elo_index: EloIndex

    def prior_counts(self, match: Match) -> tuple[int, int]:
        on = match.match_date or date.today()
        return tuple(int(self.history_index.form(pid, on)["experience"]) for pid in (match.p1_id, match.p2_id))

    def build(self, registry: ModelRegistry, match: Match, *, now: datetime | None = None) -> PredictionOutput:
        return _build_prediction(
            registry, match, self.players, self.elo, self.stats,
            self.ctx_last90, self.ctx_top20, self.ctx_top50, self.odds, self.h2h, self.history,
            asof=asof_features(self.history_index, self.elo_index, match),
            prior_matches=min_prior_matches(self.history_index, match), now=now,
        )


async def load_prediction_batch(
    db: AsyncSession, today_matches: list[Match], ref_date: date,
) -> PredictionBatch:
    """Load the slate inputs once, also used by the isolated ELO shadow CLI."""
    all_player_ids = list({pid for m in today_matches for pid in (m.p1_id, m.p2_id)})
    match_ids = [m.id for m in today_matches]

    h2h_pairs = []
    for m in today_matches:
        h2h_pairs.append((m.p1_id, m.p2_id, None))
        if m.surface:
            h2h_pairs.append((m.p1_id, m.p2_id, m.surface))

    players_cache = await player_repo.get_players_by_ids(db, all_player_ids)
    elo_cache = await player_repo.get_latest_elo_batch(db, all_player_ids)
    stats_cache = await player_repo.get_rolling_stats_batch_all_surfaces(db, all_player_ids, "last_52w")
    ctx_last90_cache = await player_repo.get_contextual_rolling_stats_batch(
        db, all_player_ids, "last90d", "overall", split_values=["all"]
    )
    ctx_top20_cache = await player_repo.get_contextual_rolling_stats_batch(
        db, all_player_ids, "last_52w", "opp_rank", split_values=["top20"]
    )
    ctx_top50_cache = await player_repo.get_contextual_rolling_stats_batch(
        db, all_player_ids, "last_52w", "opp_rank", split_values=["top50"]
    )
    odds_cache = await match_repo.get_latest_odds_batch(db, match_ids)
    h2h_cache = await match_repo.get_h2h_batch(db, h2h_pairs)
    history_cache = await match_repo.get_player_match_history_batch(db, all_player_ids, ref_date)
    history_index, elo_index = await _history_cache.get(db)

    return PredictionBatch(
        players_cache, elo_cache, stats_cache, ctx_last90_cache, ctx_top20_cache, ctx_top50_cache,
        odds_cache, h2h_cache, history_cache, history_index, elo_index,
    )


async def predict_matches(
    db: AsyncSession, registry: ModelRegistry, today_matches: list[Match], ref_date: date,
) -> list[PredictionOutput]:
    """The slate and match page use one batch path; model inference stays off the event loop."""
    if not today_matches:
        return []
    batch = await load_prediction_batch(db, today_matches, ref_date)

    def predict_all() -> list[PredictionOutput]:
        results = []
        for match in today_matches:
            try:
                results.append(batch.build(registry, match))
            except Exception:
                logger.exception("Skipping prediction for match %s", match.id)
        return results

    return await asyncio.to_thread(predict_all)
