"""
train_model.py — LightGBM tennis match prediction training pipeline.

Exports training data from PostgreSQL, trains tour-split LightGBM models
with Optuna hyperparameter tuning, walk-forward CV, and calibration.

Run:
    python train_model.py                          # train both ATP & WTA
    python train_model.py --tour ATP               # ATP only
    python train_model.py --tour WTA --no-optuna   # WTA, skip Optuna
    python train_model.py --export-only            # just dump CSV
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

try:
    import optuna
except ImportError:
    optuna = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("train_model")

MODELS_DIR = Path(__file__).parent / "models"

# Bundles are written under this version. v5 is deliberately skipped over rather than
# overwritten: it is the 217-row model this rebuild exists to replace, and keeping it on
# disk preserves the evidence of what went wrong.
MODEL_VERSION = "v6"

# Feature lists per tour.
#
# Every feature here is knowable when the match starts. The TennisAbstract serve and
# return statistics that earlier versions used are gone: player_rolling_stats holds only
# a current snapshot that is overwritten in place, so a 2023 match was being described by
# 2026 form. Head-to-head is likewise rebuilt from match results rather than read from the
# `h2h` running total, which already counted the match being predicted.
#
# The de-vigged market price is also deliberately absent. It was a model input AND a
# separate ensemble component, so the market was counted twice and the model could not
# disagree with it. Keeping ML market-free makes ELO, ML, and market three independent
# views, which is what the ensemble assumes it is blending. Backfilled matches carry no
# odds anyway, since The Odds API does not serve history.
_SHARED_FEATURES = [
    "d_elo", "d_surface_elo", "has_p1_elo", "has_p2_elo", "has_both_elo",
    "d_elo_computed", "d_surface_elo_computed",
    "d_rank_log", "d_age",
    "d_experience", "d_rest_days", "d_matches_10d", "d_matches_30d", "d_streak",
    "d_win_rate_last_20", "d_win_rate_surface",
    "h2h_total_matches", "h2h_p1_win_pct",
    "h2h_surface_matches", "h2h_surface_p1_win_pct",
    "is_clay", "is_grass", "is_grand_slam", "round_ordinal", "tournament_tier",
]

ATP_FEATURES = [*_SHARED_FEATURES, "best_of"]

WTA_FEATURES = [*_SHARED_FEATURES, "d_win_rate_last_3"]

MONOTONE_CONSTRAINTS_MAP = {
    "d_elo": 1, "d_surface_elo": 1, "d_rank_log": 1,
    "d_win_rate_last_20": 1, "d_win_rate_surface": 1,
    "h2h_p1_win_pct": 1, "h2h_surface_p1_win_pct": 1,
    "d_streak": 1, "d_win_rate_last_3": 1,
}

ROUND_ORDINALS = {
    "RR": 0, "Round Robin": 0, "Q1": 1, "Q2": 2, "Q3": 3,
    "R128": 1, "R64": 2, "R32": 3, "R16": 4, "Round of 16": 4,
    "QF": 5, "Quarterfinal": 5, "Quarterfinals": 5,
    "SF": 6, "Semifinal": 6, "Semifinals": 6,
    "F": 7, "Final": 7, "G": 7,
}

GRAND_SLAM_KEYWORDS = {"australian open", "french open", "roland garros", "wimbledon", "us open"}
MASTERS_KEYWORDS = {
    "indian wells", "miami", "monte carlo", "monte-carlo", "madrid", "rome",
    "internazionali", "montreal", "toronto", "canada", "canadian open",
    "national bank open", "cincinnati", "shanghai", "paris",
}
ATP_500_KEYWORDS = {
    "500", "dubai", "acapulco", "barcelona", "queen", "halle", "hamburg",
    "washington", "beijing", "tokyo", "vienna", "basel",
}


# =============================================================================
# Data export from PostgreSQL
# =============================================================================

EXPORT_SQL = """
WITH match_data AS (
    SELECT
        m.id AS match_id,
        m.match_date,
        m.tour,
        m.surface,
        m.tournament,
        m.round,
        m.best_of,
        m.p1_id,
        m.p2_id,
        m.p1_rank,
        m.p2_rank,
        m.winner_id,
        p1.birth_date AS p1_birth_date,
        p2.birth_date AS p2_birth_date
    FROM matches m
    JOIN players p1 ON p1.id = m.p1_id
    JOIN players p2 ON p2.id = m.p2_id
    WHERE m.status = 'completed'
      AND m.winner_id IS NOT NULL
      AND m.tour IN ('ATP', 'WTA')
    ORDER BY m.match_date
)
SELECT * FROM match_data;
"""

ELO_SQL = """
SELECT DISTINCT ON (player_id)
    player_id, elo, elo_hard, elo_clay, elo_grass, as_of_date
FROM player_elo
WHERE player_id = ANY(:pids) AND as_of_date <= :dt
ORDER BY player_id, as_of_date DESC;
"""

ROLLING_STATS_SQL = """
SELECT DISTINCT ON (player_id, surface, stat_period, split_type, split_value)
    player_id, surface, stat_period, split_type, split_value,
    win_rate, svc_pts_won, ret_pts_won,
    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
    first_in_pct, first_won_pct, second_won_pct, dominance_ratio
FROM player_rolling_stats
WHERE player_id = ANY(:pids)
  AND (
    (split_type = 'overall' AND split_value = 'all' AND stat_period IN ('last_52w', 'last90d'))
    OR (split_type = 'opp_rank' AND split_value IN ('top20', 'top50') AND stat_period = 'last_52w')
  )
ORDER BY player_id, surface, stat_period, split_type, split_value, computed_at DESC;
"""

H2H_SQL = """
SELECT p1_id, p2_id, surface, p1_wins, p2_wins
FROM h2h
WHERE (p1_id = :p1 AND p2_id = :p2) OR (p1_id = :p2 AND p2_id = :p1);
"""

ODDS_SQL = """
SELECT DISTINCT ON (match_id)
    match_id, p1_odds, p2_odds
FROM match_odds
WHERE match_id = ANY(:mids) AND market = 'moneyline'
ORDER BY match_id, fetched_at DESC;
"""

MATCH_HISTORY_SQL = """
SELECT
    MAX(match_date) AS last_match_date,
    COUNT(*) AS total_matches,
    COUNT(*) FILTER (WHERE match_date >= :dt - 10) AS m10d,
    COUNT(*) FILTER (WHERE match_date >= :dt - 30) AS m30d
FROM matches
WHERE (p1_id = :pid OR p2_id = :pid)
  AND status = 'completed'
  AND match_date < :dt;
"""

STREAK_SQL = """
SELECT winner_id FROM matches
WHERE (p1_id = :pid OR p2_id = :pid)
  AND status = 'completed'
  AND match_date < :dt
  AND winner_id IS NOT NULL
ORDER BY match_date DESC, id DESC
LIMIT 20;
"""



ALL_MATCHES_SQL = """
SELECT match_date, p1_id, p2_id, winner_id, surface
FROM matches
WHERE status = 'completed' AND winner_id IS NOT NULL
ORDER BY match_date;
"""

ALL_ELO_SQL = """
SELECT player_id, as_of_date, elo, elo_hard, elo_clay, elo_grass
FROM player_elo
ORDER BY player_id, as_of_date;
"""


def _elo_as_of(elo_hist: dict, player_id: int, on: "date"):
    """Newest ELO snapshot published on or before `on`, or None."""
    snaps = elo_hist.get(player_id)
    if not snaps:
        return None
    lo, hi = 0, len(snaps)
    while lo < hi:
        mid = (lo + hi) // 2
        if snaps[mid][0] <= on:
            lo = mid + 1
        else:
            hi = mid
    return snaps[lo - 1] if lo else None


async def export_training_data(output_path: Path) -> pd.DataFrame:
    """Export completed matches with as-of-date features only.

    Every feature here is knowable the moment the match starts. Head-to-head and form
    come from the match history via HistoryIndex rather than from the `h2h` and
    `player_rolling_stats` snapshot tables, which hold only a current view and would
    otherwise hand a 2023 match its 2026 record, including the result being predicted.

    The TennisAbstract serve and return statistics are deliberately absent: only current
    aggregates are stored and they are overwritten in place, so there is no way to
    reconstruct what they were on an old match date.
    """
    from sqlalchemy import text as sa_text
    from app.db.pool import SessionLocal
    from app.ml.asof_features import HistoryIndex, h2h_win_pct
    from app.ml.elo_history import EloIndex
    from app.ml.feature_contract import is_grand_slam, round_ordinal, tournament_tier
    import math

    logger.info("Exporting training data from database...")

    async with SessionLocal() as db:
        result = await db.execute(sa_text(EXPORT_SQL))
        matches = result.fetchall()
        cols = list(result.keys())

        history_rows = (await db.execute(sa_text(ALL_MATCHES_SQL))).fetchall()
        elo_rows = (await db.execute(sa_text(ALL_ELO_SQL))).fetchall()

    logger.info("Found %d completed ATP/WTA matches", len(matches))
    logger.info("Building history index from %d completed matches", len(history_rows))
    index = HistoryIndex(history_rows)
    # Scraped ELO only reaches back to 2026, so most backfilled matches have none.
    # Computed ELO is denser but noisier (0.44 correlation with the scraped series on
    # the overlap), so both are offered and the model decides which to trust.
    computed_elo = EloIndex(history_rows)

    elo_hist: dict[int, list] = {}
    for r in elo_rows:
        elo_hist.setdefault(r[0], []).append((r[1], r[2], r[3], r[4], r[5]))

    match_df = pd.DataFrame(matches, columns=cols)

    rows = []
    for _, m in match_df.iterrows():
        match_date = m["match_date"]
        p1_id, p2_id = int(m["p1_id"]), int(m["p2_id"])
        surface = (m["surface"] or None)
        surf_lower = (m["surface"] or "").lower()
        tourn = (m["tournament"] or "").lower()
        feat: dict[str, Optional[float]] = {}

        # ── ELO, as of the match date ────────────────────────────────────────
        p1_elo = _elo_as_of(elo_hist, p1_id, match_date)
        p2_elo = _elo_as_of(elo_hist, p2_id, match_date)
        feat["has_p1_elo"] = 1.0 if p1_elo else 0.0
        feat["has_p2_elo"] = 1.0 if p2_elo else 0.0
        feat["has_both_elo"] = 1.0 if (p1_elo and p2_elo) else 0.0
        feat["d_elo"] = (p1_elo[1] - p2_elo[1]) if (p1_elo and p2_elo and p1_elo[1] and p2_elo[1]) else None
        surf_col = {"hard": 2, "clay": 3, "grass": 4}.get(surf_lower)
        if p1_elo and p2_elo and surf_col and p1_elo[surf_col] and p2_elo[surf_col]:
            feat["d_surface_elo"] = p1_elo[surf_col] - p2_elo[surf_col]
        else:
            feat["d_surface_elo"] = None

        c1 = computed_elo.rating(p1_id, match_date)
        c2 = computed_elo.rating(p2_id, match_date)
        feat["d_elo_computed"] = (c1 - c2) if (c1 is not None and c2 is not None) else None
        cs1 = computed_elo.surface_rating(p1_id, surface, match_date)
        cs2 = computed_elo.surface_rating(p2_id, surface, match_date)
        feat["d_surface_elo_computed"] = (cs1 - cs2) if (cs1 is not None and cs2 is not None) else None

        # ── Static context ───────────────────────────────────────────────────
        if m["p1_rank"] and m["p2_rank"] and m["p1_rank"] > 0 and m["p2_rank"] > 0:
            feat["d_rank_log"] = math.log(m["p2_rank"]) - math.log(m["p1_rank"])
        else:
            feat["d_rank_log"] = None

        if m["p1_birth_date"] and m["p2_birth_date"]:
            feat["d_age"] = (
                (match_date - m["p1_birth_date"]).days - (match_date - m["p2_birth_date"]).days
            ) / 365.25
        else:
            feat["d_age"] = None

        feat["is_clay"] = 1.0 if surf_lower == "clay" else 0.0
        feat["is_grass"] = 1.0 if surf_lower == "grass" else 0.0
        feat["is_grand_slam"] = is_grand_slam(m["tournament"])
        feat["round_ordinal"] = round_ordinal(m["round"])
        feat["tournament_tier"] = float(tournament_tier(m["tournament"] or ""))
        feat["best_of"] = float(m["best_of"] or 3)

        # ── Form, from matches played before this one ────────────────────────
        f1 = index.form(p1_id, match_date, surface)
        f2 = index.form(p2_id, match_date, surface)

        def _diff(key: str) -> Optional[float]:
            a, b = f1[key], f2[key]
            return None if (a is None or b is None) else a - b

        feat["d_experience"] = _diff("experience")
        feat["d_rest_days"] = _diff("rest_days")
        feat["d_matches_10d"] = _diff("matches_10d")
        feat["d_matches_30d"] = _diff("matches_30d")
        feat["d_streak"] = _diff("streak")
        feat["d_win_rate_last_20"] = _diff("win_rate_last_20")
        feat["d_win_rate_last_3"] = _diff("win_rate_last_3")
        feat["d_win_rate_surface"] = _diff("win_rate_surface")

        # ── Head to head, before this meeting ────────────────────────────────
        h1, h2 = index.h2h(p1_id, p2_id, match_date)
        feat["h2h_total_matches"] = float(h1 + h2)
        feat["h2h_p1_win_pct"] = h2h_win_pct(h1, h2)
        s1, s2 = index.h2h(p1_id, p2_id, match_date, surface=surface) if surface else (0, 0)
        feat["h2h_surface_matches"] = float(s1 + s2)
        feat["h2h_surface_p1_win_pct"] = h2h_win_pct(s1, s2)

        feat["match_id"] = int(m["match_id"])
        feat["match_date"] = match_date
        feat["tour"] = m["tour"]
        feat["label"] = 1.0 if m["winner_id"] == p1_id else 0.0
        rows.append(feat)

        if len(rows) % 5000 == 0:
            logger.info("  processed %d / %d matches", len(rows), len(match_df))

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    logger.info("Exported %d rows to %s", len(df), output_path)
    return df



# =============================================================================
# Training
# =============================================================================

# Matches ModelRegistry.MIN_TRAINING_ROWS: a bundle thinner than this is refused at load,
# so there is no point writing one.
MIN_TRAINING_ROWS = 5000

# p1-relative features that have no p2 counterpart to swap with, so mirroring takes the
# complement instead.
_COMPLEMENT_ON_MIRROR = {"h2h_p1_win_pct", "h2h_surface_p1_win_pct"}


def _mirror_feature(name: str, df: pd.DataFrame, features: list[str]) -> pd.Series:
    """The value `name` should take when p1 and p2 swap places."""
    if name.startswith("d_"):
        return -df[name]
    if name in _COMPLEMENT_ON_MIRROR:
        return 1.0 - df[name]
    for a, b in (("p1", "p2"), ("p2", "p1")):
        if a in name:
            counterpart = name.replace(a, b)
            if counterpart in features and counterpart in df.columns:
                return df[counterpart]
    return df[name]


def _augment_mirrored(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Append a p1/p2-swapped copy of every row with the label flipped.

    The model sees only p1-relative differences, so without this it can learn that p1
    simply wins more often, which is an artifact of ingest ordering rather than tennis.
    Mirroring makes the training set symmetric and doubles it at no data cost.
    """
    if df.empty:
        return df
    mirrored = df.copy()
    for f in features:
        mirrored[f] = _mirror_feature(f, df, features)
    mirrored["label"] = 1.0 - df["label"]
    return pd.concat([df, mirrored], ignore_index=True).sort_values("match_date").reset_index(drop=True)


def _get_monotone_constraints(features: list[str]) -> list[int]:
    return [MONOTONE_CONSTRAINTS_MAP.get(f, 0) for f in features]


def _split_time_series(df: pd.DataFrame, val_days: int = 180, test_days: int = 180,
                       early_stop_days: int = 120):
    """Time-based train/val/test split."""
    df = df.sort_values("match_date").reset_index(drop=True)
    max_date = df["match_date"].max()
    test_start = max_date - timedelta(days=test_days)
    val_start = test_start - timedelta(days=val_days)
    es_start = val_start - timedelta(days=early_stop_days)

    train = df[df["match_date"] < es_start]
    early_stop = df[(df["match_date"] >= es_start) & (df["match_date"] < val_start)]
    val = df[(df["match_date"] >= val_start) & (df["match_date"] < test_start)]
    test = df[df["match_date"] >= test_start]

    return train, early_stop, val, test


def _eval_metrics(y_true, y_prob):
    return {
        "accuracy": float(accuracy_score(y_true, (np.array(y_prob) >= 0.5).astype(int))),
        "log_loss": float(log_loss(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "auc": float(roc_auc_score(y_true, y_prob)),
    }


def _calibration_report(y_true, y_prob, n_bins: int = 10):
    bins = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() > 0:
            bins.append({
                "bin_start": lo, "bin_end": hi,
                "mean_predicted": float(y_prob[mask].mean()),
                "mean_actual": float(y_true[mask].mean()),
                "count": int(mask.sum()),
            })
    return bins


def _walk_forward_cv(df: pd.DataFrame, features: list[str], params: dict,
                     n_folds: int = 5) -> list[dict]:
    """Walk-forward time-series cross-validation."""
    df = df.sort_values("match_date").reset_index(drop=True)
    dates = df["match_date"].values
    total = len(df)
    fold_size = total // (n_folds + 1)

    results = []
    mc = _get_monotone_constraints(features)

    for fold in range(n_folds):
        train_end = (fold + 1) * fold_size
        test_end = min((fold + 2) * fold_size, total)

        train_df = df.iloc[:train_end]
        test_df = df.iloc[train_end:test_end]

        if len(test_df) == 0:
            continue

        X_train = train_df[features].values.astype(np.float32)
        y_train = train_df["label"].values
        X_test = test_df[features].values.astype(np.float32)
        y_test = test_df["label"].values

        dtrain = lgb.Dataset(X_train, label=y_train, feature_name=features)
        model = lgb.train(
            {**params, "monotone_constraints": mc},
            dtrain, num_boost_round=params.get("n_estimators", 1500),
        )
        y_prob = model.predict(X_test)
        metrics = _eval_metrics(y_test, y_prob)
        metrics["train_size"] = len(train_df)
        metrics["test_size"] = len(test_df)
        metrics["test_start"] = str(test_df["match_date"].min())
        metrics["test_end"] = str(test_df["match_date"].max())
        results.append(metrics)
        logger.info("  Fold %d: acc=%.3f auc=%.3f (train=%d test=%d)",
                     fold + 1, metrics["accuracy"], metrics["auc"],
                     len(train_df), len(test_df))

    return results


def _optuna_tune(X_train, y_train, X_val, y_val, features: list[str],
                 n_trials: int = 80) -> dict:
    """Optuna hyperparameter search for LightGBM."""
    if optuna is None:
        raise RuntimeError("Optuna is not installed")
    mc = _get_monotone_constraints(features)

    def objective(trial):
        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "verbosity": -1,
            "boosting_type": "gbdt",
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 4, 32),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 500, 3000),
            "monotone_constraints": mc,
        }

        dtrain = lgb.Dataset(X_train, label=y_train, feature_name=features)
        dval = lgb.Dataset(X_val, label=y_val, feature_name=features, reference=dtrain)

        callbacks = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)]
        model = lgb.train(
            params, dtrain, num_boost_round=params["n_estimators"],
            valid_sets=[dval], callbacks=callbacks,
        )
        y_prob = model.predict(X_val)
        return log_loss(y_val, y_prob)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)

    best = study.best_params
    best["objective"] = "binary"
    best["metric"] = "binary_logloss"
    best["verbosity"] = -1
    best["boosting_type"] = "gbdt"
    logger.info("Optuna best params: %s (log_loss=%.4f)", best, study.best_value)
    return best


def train_tour(df: pd.DataFrame, tour: str, features: list[str],
               use_optuna: bool = True, n_optuna_trials: int = 80) -> dict:
    """Train a LightGBM model for a single tour."""
    logger.info("=" * 60)
    logger.info("Training %s model (%d features)", tour, len(features))

    tour_df = df[df["tour"] == tour].copy()
    logger.info("  %d matches for %s", len(tour_df), tour)

    if len(tour_df) < MIN_TRAINING_ROWS:
        raise ValueError(
            f"{tour}: {len(tour_df)} matches is below the {MIN_TRAINING_ROWS} minimum. "
            f"v5 was trained on 217 and scored 0.56 walk-forward AUC against v4's 0.76. "
            f"Backfill history first: python -m app.ingest.livetennis --from YYYY-MM-DD "
            f"--to YYYY-MM-DD --chunk-days 30"
        )

    # Missing means missing, not zero. LightGBM learns a default split direction for NaN;
    # filling with 0.0 tells the model that e.g. market_ml_p1_no_vig is a 0% chance.
    for f in features:
        if f not in tour_df.columns:
            tour_df[f] = np.nan
        else:
            tour_df[f] = pd.to_numeric(tour_df[f], errors="coerce")

    train, early_stop, val, test = _split_time_series(tour_df)
    logger.info("  Split: train=%d, early_stop=%d, val=%d, test=%d",
                len(train), len(early_stop), len(val), len(test))

    if min(len(train), len(early_stop), len(val), len(test)) == 0:
        span = (tour_df["match_date"].max() - tour_df["match_date"].min()).days
        raise ValueError(
            f"{tour}: the time-based split produced an empty partition over a {span}-day "
            f"span. The old proportional fallback hid exactly this, which is how v5 shipped "
            f"trained and 'tested' on the same three weeks. Widen the backfill window."
        )

    # Only the fitting partitions get mirrored. Doing it to val/test would just score the
    # same match twice in opposite orientations and inflate confidence in the metrics.
    train = _augment_mirrored(train, features)
    early_stop = _augment_mirrored(early_stop, features)
    logger.info("  After mirroring: train=%d, early_stop=%d", len(train), len(early_stop))

    X_train = train[features].values.astype(np.float32)
    y_train = train["label"].values
    X_es = early_stop[features].values.astype(np.float32)
    y_es = early_stop["label"].values
    X_val = val[features].values.astype(np.float32)
    y_val = val["label"].values
    X_test = test[features].values.astype(np.float32)
    y_test = test["label"].values

    if use_optuna and optuna is None:
        logger.warning("  Optuna is not installed; falling back to base parameters")
        use_optuna = False

    # Combine train + early_stop for Optuna (use val for evaluation)
    X_train_full = np.vstack([X_train, X_es])
    y_train_full = np.concatenate([y_train, y_es])

    mc = _get_monotone_constraints(features)

    if use_optuna:
        logger.info("  Running Optuna (%d trials)...", n_optuna_trials)
        params = _optuna_tune(X_train_full, y_train_full, X_val, y_val,
                              features, n_optuna_trials)
    else:
        params = {
            "objective": "binary", "metric": "binary_logloss", "verbosity": -1,
            "boosting_type": "gbdt", "learning_rate": 0.05, "num_leaves": 8,
            "max_depth": 5, "min_child_samples": 50, "subsample": 0.8,
            "colsample_bytree": 0.8, "reg_alpha": 0.1, "reg_lambda": 1.0,
            "n_estimators": 1500,
        }

    # Final training with early stopping
    n_est = params.pop("n_estimators", 1500)
    dtrain = lgb.Dataset(X_train, label=y_train, feature_name=features)
    des = lgb.Dataset(X_es, label=y_es, feature_name=features, reference=dtrain)

    callbacks = [lgb.early_stopping(100, verbose=False), lgb.log_evaluation(100)]
    model = lgb.train(
        {**params, "monotone_constraints": mc},
        dtrain, num_boost_round=n_est,
        valid_sets=[des], callbacks=callbacks,
    )

    # Evaluate
    y_val_prob = model.predict(X_val)
    y_test_prob = model.predict(X_test)
    val_metrics = _eval_metrics(y_val, y_val_prob)
    test_metrics = _eval_metrics(y_test, y_test_prob)
    logger.info("  Val:  acc=%.3f auc=%.3f logloss=%.4f",
                val_metrics["accuracy"], val_metrics["auc"], val_metrics["log_loss"])
    logger.info("  Test: acc=%.3f auc=%.3f logloss=%.4f",
                test_metrics["accuracy"], test_metrics["auc"], test_metrics["log_loss"])

    # Calibration: Platt scaling fit on the validation predictions.
    #
    # This used to wrap LogisticRegression in CalibratedClassifierCV(cv="prefit"), which
    # sklearn 1.8 removed. The wrapper was doing nothing useful anyway: with cv="prefit"
    # and a one-column input of predicted probabilities, it is just fitting a logistic
    # curve from raw probability to outcome. Fitting that directly is the same thing and
    # keeps the predict_proba interface ModelRegistry expects.
    calib_method = "sigmoid"
    try:
        from sklearn.linear_model import LogisticRegression
        calib_model = LogisticRegression()
        calib_model.fit(y_val_prob.reshape(-1, 1), y_val)
        y_test_calib = calib_model.predict_proba(y_test_prob.reshape(-1, 1))[:, 1]
        test_calib_metrics = _eval_metrics(y_test, y_test_calib)
        logger.info("  Test (calibrated): acc=%.3f auc=%.3f logloss=%.4f",
                     test_calib_metrics["accuracy"], test_calib_metrics["auc"],
                     test_calib_metrics["log_loss"])

        # Only use calibration if it improves log_loss
        use_calibration = test_calib_metrics["log_loss"] < test_metrics["log_loss"]
        if not use_calibration:
            logger.info("  Calibration did NOT improve log_loss, using raw probs")
            calib_model = None
            test_calib_metrics = test_metrics
    except Exception as e:
        logger.warning("  Calibration failed: %s", e)
        calib_model = None
        test_calib_metrics = test_metrics

    # Walk-forward CV
    logger.info("  Running walk-forward CV...")
    wf_results = _walk_forward_cv(tour_df, features, {**params, "n_estimators": n_est})
    wf_mean = {k: float(np.mean([r[k] for r in wf_results]))
               for k in ["accuracy", "log_loss", "brier", "auc"]}
    wf_std = {k: float(np.std([r[k] for r in wf_results]))
              for k in ["accuracy", "log_loss", "brier", "auc"]}

    # Feature importance
    importance = dict(zip(features, model.feature_importance(importance_type="gain")))
    importance = dict(sorted(importance.items(), key=lambda x: -x[1]))

    # Betting simulation
    betting_sim = {}
    for thresh in [0.55, 0.60, 0.65, 0.70]:
        mask = (y_test_prob >= thresh) | (y_test_prob <= 1 - thresh)
        if mask.sum() > 0:
            preds = (y_test_prob[mask] >= 0.5).astype(int)
            betting_sim[str(thresh)] = {
                "bets": int(mask.sum()),
                "wins": int((preds == y_test[mask]).sum()),
                "accuracy": float((preds == y_test[mask]).mean()),
                "threshold": thresh,
            }

    # Save artifacts
    version = MODEL_VERSION
    tour_lower = tour.lower()
    model_path = MODELS_DIR / f"lgbm_tennis_{version}_{tour_lower}.txt"
    feat_path = MODELS_DIR / f"lgbm_tennis_{version}_{tour_lower}_features.txt"
    meta_path = MODELS_DIR / f"lgbm_tennis_{version}_{tour_lower}_meta.json"
    calib_path = MODELS_DIR / f"lgbm_tennis_{version}_{tour_lower}_calibration.joblib"

    model.save_model(str(model_path))
    feat_path.write_text("\n".join(features) + "\n")

    if calib_model:
        joblib.dump(calib_model, calib_path)
        logger.info("  Saved calibration to %s", calib_path)

    meta = {
        "model_version": version,
        "engine": "lgbm",
        "tour_split": tour,
        "num_features": len(features),
        "features": features,
        # How absent features were encoded during training. Inference must match, or the
        # model reads "unknown" as a real extreme value. Bundles without this key predate
        # the change and were trained with zero-fill.
        "missing_value_fill": "nan",
        "mirrored_training_rows": True,
        "rows": {
            "total": len(tour_df),
            "train": len(train),
            "val": len(val),
            "test": len(test),
            "train_fit": len(train),
            "early_stop": len(early_stop),
        },
        "metrics": {
            "val": val_metrics,
            "test": test_metrics,
            "test_calibrated": test_calib_metrics,
        },
        "calibration_report": {"bins": _calibration_report(y_test, y_test_prob)},
        "walk_forward_cv": {
            "folds": wf_results,
            "mean": wf_mean,
            "std": wf_std,
        },
        "betting_simulation": betting_sim,
        "feature_importance_gain": {k: str(int(v)) for k, v in importance.items()},
        "calibration": calib_method if calib_model else "none",
        "optuna_tuned": use_optuna,
        "params": {k: v for k, v in params.items()
                   if k not in ("monotone_constraints",)},
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    logger.info("  Saved model to %s", model_path)
    logger.info("  Saved meta to %s", meta_path)

    return meta


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Train LightGBM tennis prediction models")
    parser.add_argument("--tour", choices=["ATP", "WTA"], help="Train single tour only")
    parser.add_argument("--no-optuna", action="store_true", help="Skip Optuna tuning")
    parser.add_argument("--optuna-trials", type=int, default=80, help="Optuna trial count")
    parser.add_argument("--export-only", action="store_true", help="Only export CSV")
    parser.add_argument("--csv", type=str, help="Use existing CSV instead of DB export")
    args = parser.parse_args()

    csv_path = Path(args.csv) if args.csv else MODELS_DIR / f"tennis_training_{MODEL_VERSION}.csv"

    if args.csv and Path(args.csv).exists():
        logger.info("Loading existing CSV: %s", args.csv)
        df = pd.read_csv(args.csv, parse_dates=["match_date"])
    else:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        df = asyncio.run(export_training_data(csv_path))

    if args.export_only:
        logger.info("Export complete. Exiting.")
        return

    tours = [args.tour] if args.tour else ["ATP", "WTA"]
    for tour in tours:
        features = ATP_FEATURES if tour == "ATP" else WTA_FEATURES
        train_tour(df, tour, features,
                   use_optuna=not args.no_optuna,
                   n_optuna_trials=args.optuna_trials)

    logger.info("Training complete!")


if __name__ == "__main__":
    main()
