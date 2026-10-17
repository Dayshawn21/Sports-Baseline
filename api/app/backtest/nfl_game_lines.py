"""Backtest team ELO and scoring ratings against NFLverse closing game lines.

Every configuration is fitted on the fit seasons only; the holdout seasons are
scored once with the chosen configuration. Tuning against the holdout would
turn it into a second fit set and make the adoption decision meaningless.

Run from api/: python -m app.backtest.nfl_game_lines
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from typing import Literal

from app.core.nfl_elo import NflEloConfig, expected_home_win_probability, replay as replay_elo
from app.core.nfl_game_context import NflSpreadFeatures, NflTotalFeatures, spread_features, total_features
from app.core.nfl_game_lines import (
    NflGameLineGame, PickRecord, blend, elo_margin, mae, market_home_probability, pick_record,
)
from app.core.nfl_scoring_ratings import NflScoringConfig, replay as replay_scoring
from app.core.nfl_td_backtest import brier, log_loss

# 2012-2013 are ELO burn-in: every team started 2012 at the same rating.
FIT_SEASONS = frozenset(range(2014, 2022))
HOLDOUT_SEASONS = frozenset(range(2022, 2026))

# Pre-registered in the 24b spec before any holdout number existed. Do not edit
# after the holdout run: a changed grid or rule invalidates the decision.
ELO_GRID = tuple(
    NflEloConfig(k, home_field, regression)
    for k in (15.0, 20.0, 25.0)
    for home_field in (24.0, 36.0, 48.0, 60.0)
    for regression in (0.25, 1 / 3, 0.5)
)
LEARNING_RATE_GRID = (0.05, 0.1, 0.15, 0.2)
BLEND_WEIGHT_GRID = tuple(step / 10 for step in range(11))
PICK_THRESHOLDS = (1.5, 3.0)
ADOPTION_THRESHOLD = 3.0
ADOPTION_MIN_PICKS = 100
# -110 on both sides breaks even at 110 / 210 = 52.38%.
ADOPTION_HIT_RATE = 0.524

WeekBucket = Literal["1-4", "5+"]
Arm = Literal["moneyline", "spread", "total"]
BUCKETS: tuple[WeekBucket, ...] = ("1-4", "5+")
ARMS: tuple[Arm, ...] = ("moneyline", "spread", "total")


@dataclass(frozen=True)
class NflGameLineCase:
    game_key: str
    season: int
    week_bucket: WeekBucket
    home_won: bool | None  # None on a tie
    home_margin: int
    total_points: int
    market_home_probability: float | None
    spread_line: float | None
    total_line: float | None
    elo_home_probability: float
    elo_margin: float
    model_total: float
    total_features: NflTotalFeatures
    spread_features: NflSpreadFeatures


def week_bucket(week: int) -> WeekBucket:
    return "1-4" if week <= 4 else "5+"


def build_cases(
    games: list[NflGameLineGame], elo_config: NflEloConfig, scoring_config: NflScoringConfig,
    seasons: frozenset[int],
) -> list[NflGameLineCase]:
    """One case per final game in `seasons`.

    Ratings are replayed over every game, burn-in included, so a case's inputs
    carry the full history before it. A missing line only blanks its own market.
    """
    elo_games = [line_game.game for line_game in games]
    pre_elo = {(row.game_key, row.is_home): row.elo_pre for row in replay_elo(elo_games, elo_config)}
    totals = {row.game_key: row.expected_total for row in replay_scoring(elo_games, scoring_config)}
    cases: list[NflGameLineCase] = []
    for line_game in games:
        game = line_game.game
        if game.season not in seasons or game.home_score is None or game.away_score is None:
            continue
        home_elo, visitor_elo = pre_elo[(game.game_key, True)], pre_elo[(game.game_key, False)]
        margin = game.home_score - game.away_score
        cases.append(NflGameLineCase(
            game_key=game.game_key, season=game.season, week_bucket=week_bucket(game.week),
            home_won=None if margin == 0 else margin > 0,
            home_margin=margin, total_points=game.home_score + game.away_score,
            market_home_probability=market_home_probability(line_game.home_moneyline, line_game.away_moneyline),
            spread_line=line_game.spread_line, total_line=line_game.total_line,
            elo_home_probability=expected_home_win_probability(home_elo, visitor_elo, elo_config.home_field),
            elo_margin=elo_margin(home_elo, visitor_elo, elo_config.home_field),
            model_total=totals[game.game_key],
            total_features=total_features(
                line_game.roof, line_game.temp, line_game.wind, line_game.home_rest, line_game.away_rest,
            ),
            spread_features=spread_features(line_game.home_rest, line_game.away_rest),
        ))
    return cases


def _arm_value(case: NflGameLineCase, arm: Arm) -> tuple[float, float, float] | None:
    """(model, market, actual), or None when the arm has no market or no outcome for this game.

    A moneyline actual is 1.0 or 0.0, so ties drop out of that arm only.
    """
    if arm == "moneyline":
        if case.market_home_probability is None or case.home_won is None:
            return None
        return case.elo_home_probability, case.market_home_probability, float(case.home_won)
    if arm == "spread":
        return None if case.spread_line is None else (case.elo_margin, case.spread_line, float(case.home_margin))
    return None if case.total_line is None else (case.model_total, case.total_line, float(case.total_points))


def usable_cases(cases: list[NflGameLineCase], arm: Arm) -> list[NflGameLineCase]:
    return [case for case in cases if _arm_value(case, arm) is not None]


def arm_values(cases: list[NflGameLineCase], arm: Arm) -> tuple[list[float], list[float], list[float]]:
    values = [value for case in cases if (value := _arm_value(case, arm)) is not None]
    return [v[0] for v in values], [v[1] for v in values], [v[2] for v in values]


def arm_loss(arm: Arm, predictions: list[float], actuals: list[float]) -> float:
    """Log loss for win probability, mean absolute error in points for spread and total."""
    if arm == "moneyline":
        return log_loss(predictions, [value == 1.0 for value in actuals])
    return mae(predictions, actuals)


def fit_blend_weight(cases: list[NflGameLineCase], arm: Arm) -> float:
    """Lowest-loss weight; ties keep the smaller weight, so no evidence means the market.

    Losses are rounded before comparing, or float noise in the blend would break
    a true tie in favor of an arbitrary nonzero weight.
    """
    model, market, actual = arm_values(cases, arm)
    return min(
        BLEND_WEIGHT_GRID,
        key=lambda weight: round(arm_loss(arm, [blend(m, k, weight) for m, k in zip(model, market)], actual), 12),
    )


@dataclass(frozen=True)
class NflGameLineFit:
    elo: NflEloConfig
    scoring: NflScoringConfig
    weights: dict[tuple[Arm, WeekBucket], float]


def fit(games: list[NflGameLineGame]) -> NflGameLineFit:
    """Choose every configuration from fit-season cases alone."""
    first_scoring = NflScoringConfig(LEARNING_RATE_GRID[0])

    def elo_loss(config: NflEloConfig) -> float:
        cases = [case for case in build_cases(games, config, first_scoring, FIT_SEASONS) if case.home_won is not None]
        return log_loss([case.elo_home_probability for case in cases], [bool(case.home_won) for case in cases])

    elo = min(ELO_GRID, key=elo_loss)

    def total_loss(rate: float) -> float:
        cases = build_cases(games, elo, NflScoringConfig(rate), FIT_SEASONS)
        return mae([case.model_total for case in cases], [float(case.total_points) for case in cases])

    scoring = NflScoringConfig(min(LEARNING_RATE_GRID, key=total_loss))
    fit_cases = build_cases(games, elo, scoring, FIT_SEASONS)
    weights = {
        (arm, bucket): fit_blend_weight([case for case in fit_cases if case.week_bucket == bucket], arm)
        for arm in ARMS for bucket in BUCKETS
    }
    return NflGameLineFit(elo, scoring, weights)


@dataclass(frozen=True)
class NflArmScore:
    label: str
    games: int
    market_loss: float
    model_loss: float
    blend_loss: float
    # Brier for the moneyline arm only; picks for spread and total only.
    market_brier: float | None = None
    blend_brier: float | None = None
    model_picks: dict[float, PickRecord] = field(default_factory=dict)
    blend_picks: dict[float, PickRecord] = field(default_factory=dict)


def score_arm(
    label: str, cases: list[NflGameLineCase], arm: Arm, weights: dict[tuple[Arm, WeekBucket], float],
) -> NflArmScore:
    usable = usable_cases(cases, arm)
    model, market, actual = arm_values(usable, arm)
    blended = [blend(m, k, weights[(arm, case.week_bucket)]) for m, k, case in zip(model, market, usable)]
    losses = (arm_loss(arm, market, actual), arm_loss(arm, model, actual), arm_loss(arm, blended, actual))
    if arm == "moneyline":
        outcomes = [value == 1.0 for value in actual]
        return NflArmScore(
            label, len(usable), *losses, market_brier=brier(market, outcomes), blend_brier=brier(blended, outcomes),
        )
    return NflArmScore(
        label, len(usable), *losses,
        model_picks={t: pick_record(model, market, actual, t) for t in PICK_THRESHOLDS},
        blend_picks={t: pick_record(blended, market, actual, t) for t in PICK_THRESHOLDS},
    )


def adopted(arm: Arm, overall: NflArmScore, buckets: list[NflArmScore]) -> bool:
    """The pre-registered rule. Strict improvement, so a zero blend weight (a tie) is rejected."""
    if arm == "moneyline":
        if overall.blend_brier is None or overall.market_brier is None:
            return False
        return (
            overall.blend_loss < overall.market_loss
            and overall.blend_brier < overall.market_brier
            and all(bucket.blend_loss <= bucket.market_loss for bucket in buckets)
        )
    picks = overall.blend_picks[ADOPTION_THRESHOLD]
    return (
        overall.blend_loss < overall.market_loss
        and picks.picks >= ADOPTION_MIN_PICKS
        and picks.hit_rate is not None and picks.hit_rate >= ADOPTION_HIT_RATE
    )


def _picks(record: PickRecord) -> str:
    rate = f"{record.hit_rate:.3f}" if record.hit_rate is not None else "  -  "
    return f"{rate} ({record.hits}-{record.misses}-{record.pushes})"


def _row(score: NflArmScore) -> str:
    base = f"{score.label:<12}{score.games:>6}  {score.market_loss:>8.4f} {score.model_loss:>8.4f} {score.blend_loss:>8.4f}"
    if score.market_brier is not None and score.blend_brier is not None:
        return f"{base}  {score.market_brier:>9.4f} {score.blend_brier:>9.4f}"
    return base + "  " + "  ".join(
        f"model@{t:g} {_picks(score.model_picks[t])}  blend@{t:g} {_picks(score.blend_picks[t])}"
        for t in PICK_THRESHOLDS
    )


def describe_fit(result: NflGameLineFit) -> str:
    elo = result.elo
    weights = ", ".join(f"{arm} {bucket} {weight:.1f}" for (arm, bucket), weight in result.weights.items())
    return (
        f"Fit {min(FIT_SEASONS)}-{max(FIT_SEASONS)}: ELO k {elo.k:g}, home field {elo.home_field:g}, "
        f"season regression {elo.season_regression:.3f}; scoring learning rate {result.scoring.learning_rate:g}\n"
        f"Blend weights (model share): {weights}"
    )


def report(games: list[NflGameLineGame], result: NflGameLineFit) -> str:
    """Score the holdout once with the fitted configuration."""
    holdout = build_cases(games, result.elo, result.scoring, HOLDOUT_SEASONS)
    label = f"{min(HOLDOUT_SEASONS)}-{max(HOLDOUT_SEASONS)}"
    lines = [describe_fit(result)]
    for arm in ARMS:
        overall = score_arm(label, holdout, arm, result.weights)
        buckets = [
            score_arm(f"  wk {bucket}", [case for case in holdout if case.week_bucket == bucket], arm, result.weights)
            for bucket in BUCKETS
        ]
        unit = "log loss" if arm == "moneyline" else "MAE"
        extra = "  Br market  Br blend" if arm == "moneyline" else "  hit rate (W-L-P)"
        lines += [
            "", f"{arm.upper()} ({unit}: market, model alone, blend)",
            f"{'set':<12}{'games':>6}  {'market':>8} {'model':>8} {'blend':>8}{extra}",
            _row(overall), *(_row(bucket) for bucket in buckets),
            f"Verdict: {'ADOPTED' if adopted(arm, overall, buckets) else 'rejected'}",
        ]
    return "\n".join(lines)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    parser = argparse.ArgumentParser(description="Backtest NFL game-line models against closing lines")
    parser.add_argument(
        "--signal", choices=("ratings", "context", "efficiency"), default="ratings",
        help=(
            "ratings: 24b ELO and scoring blends; context: 24e weather, roof, and rest adjustments; "
            "efficiency: 24c EPA, success rate, and pace adjustments"
        ),
    )
    parser.add_argument(
        "--dry-run-fit", action="store_true", help="print the fitted configuration without scoring the holdout",
    )
    args = parser.parse_args()
    async with SessionLocal() as db:
        games = await nfl_repo.get_game_line_games(db)
        efficiency_rows = await nfl_repo.get_team_efficiency(db) if args.signal == "efficiency" else {}
    if args.signal == "efficiency":
        from app.backtest.nfl_game_efficiency import describe_efficiency_fit, efficiency_report, fit_efficiency

        efficiency = fit_efficiency(games, efficiency_rows)
        print(describe_efficiency_fit(efficiency) if args.dry_run_fit else efficiency_report(games, efficiency_rows, efficiency))
        return
    if args.signal == "context":
        from app.backtest.nfl_game_context import context_report, describe_context_fit, fit_context

        coefficients = fit_context(games)
        print(describe_context_fit(coefficients) if args.dry_run_fit else context_report(games, coefficients))
        return
    result = fit(games)
    print(describe_fit(result) if args.dry_run_fit else report(games, result))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
