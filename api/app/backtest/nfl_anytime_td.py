"""Backtest a role signal (red-zone usage or snap share) against the production anytime-TD baseline.

Every fit uses the fit season only; the holdout season is scored once with the
chosen configuration. Tuning against the holdout would turn it into a second fit
set and make the adoption decision meaningless.

Run from api/: python -m app.backtest.nfl_anytime_td [--signal snap-share]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from functools import partial
from itertools import product
from statistics import mean

from sklearn.linear_model import LinearRegression

from app.core.nfl_red_zone import NflRedZoneCoefficients
from app.core.nfl_game_script import implied_team_points
from app.core.nfl_end_zone import NflEndZoneCoefficients
from app.core.nfl_snap_share import NflSnapCoefficients
from app.core.nfl_td_backtest import (
    EVALUATED_POSITIONS,
    END_ZONE_POSITIONS,
    SNAP_SHARE_POSITIONS,
    NflSnapRow,
    NflTdBacktestCase,
    NflTdScore,
    NflWeeklyTdRow,
    SnapForm,
    baseline_probability,
    build_cases,
    log_loss,
    red_zone_probability,
    score,
    score_by_position,
    snap_share_probability,
    implied_total_probability,
    production_probability,
    end_zone_probability,
)

BLEND_WEIGHT_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
IMPLIED_TOTAL_EXPONENT_GRID = (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
SNAP_FORMS: tuple[SnapForm, ...] = ("season", "recent")


def fit_coefficients(rows: list[NflWeeklyTdRow], season: int) -> NflRedZoneCoefficients:
    """Same-game TDs on same-game opportunities: what one opportunity is worth."""
    features, touchdowns = [], []
    for row in rows:
        rates = row.red_zone
        if row.season != season or row.position not in EVALUATED_POSITIONS or rates is None:
            continue
        features.append([
            rates.rz5_carries, rates.rz20_carries - rates.rz5_carries,
            rates.rz5_targets, rates.rz20_targets - rates.rz5_targets,
        ])
        touchdowns.append(row.touchdowns)
    model = LinearRegression(positive=True).fit(features, touchdowns)
    return NflRedZoneCoefficients(float(model.intercept_), *(float(value) for value in model.coef_))


def choose_blend_weight(cases: list[NflTdBacktestCase], coefficients: NflRedZoneCoefficients) -> float:
    outcomes = [case.scored for case in cases]

    def fit_loss(weight: float) -> float:
        return log_loss([red_zone_probability(case, coefficients, weight) for case in cases], outcomes)

    return min(BLEND_WEIGHT_GRID, key=fit_loss)


def _line(label: str, baseline: NflTdScore, signal: NflTdScore) -> str:
    return (
        f"{label:<14}{baseline.games:>7}  "
        f"{baseline.log_loss:>9.5f} {signal.log_loss:>9.5f} {signal.log_loss - baseline.log_loss:>+9.5f}  "
        f"{baseline.brier:>8.5f} {signal.brier:>8.5f} {signal.brier - baseline.brier:>+9.5f}  "
        f"{baseline.mean_predicted:>6.3f} {signal.mean_predicted:>6.3f} {baseline.actual_rate:>6.3f}"
    )


def _header(signal: str) -> str:
    return (
        f"{'set':<14}{'games':>7}  {'LL base':>9} {'LL ' + signal:>9} {'LL diff':>9}  "
        f"{'Br base':>8} {'Br ' + signal:>8} {'Br diff':>9}  {'p base':>6} {'p ' + signal:>6} {'actual':>6}"
    )


def report(rows: list[NflWeeklyTdRow], fit_season: int, holdout_season: int) -> str:
    coefficients = fit_coefficients(rows, fit_season)
    fit_cases = build_cases(rows, frozenset({fit_season}))
    holdout_cases = build_cases(rows, frozenset({holdout_season}))
    weight = choose_blend_weight(fit_cases, coefficients)
    red_zone = partial(red_zone_probability, coefficients=coefficients, blend_weight=weight)

    lines = [
        f"Coefficients (fit {fit_season}, TDs per game): intercept {coefficients.intercept:.4f}, "
        f"rz5 carry {coefficients.rz5_carry:.4f}, rz6-20 carry {coefficients.rz6_20_carry:.4f}, "
        f"rz5 target {coefficients.rz5_target:.4f}, rz6-20 target {coefficients.rz6_20_target:.4f}",
        f"Blend weight (by {fit_season} log loss): {weight:.1f}",
        "",
        _header("rz"),
        _line(f"{fit_season} fit", score(fit_cases, baseline_probability), score(fit_cases, red_zone)),
        _line(f"{holdout_season} holdout", score(holdout_cases, baseline_probability), score(holdout_cases, red_zone)),
    ]
    baseline_positions = score_by_position(holdout_cases, baseline_probability)
    red_zone_positions = score_by_position(holdout_cases, red_zone)
    for position, baseline_score in baseline_positions.items():
        lines.append(_line(f"  {holdout_season} {position}", baseline_score, red_zone_positions[position]))
    return "\n".join(lines)


def fit_snap_coefficients(
    rows: list[NflWeeklyTdRow], snap_rows: list[NflSnapRow], season: int,
) -> dict[str, NflSnapCoefficients]:
    """Per position, same-game TDs on same-game snap share over weekly rows that have a snap row."""
    shares = {
        (snap.player_id, snap.season, snap.week): snap.offense_pct
        for snap in snap_rows if snap.season == season and snap.offense_pct is not None
    }
    coefficients: dict[str, NflSnapCoefficients] = {}
    for position in sorted(SNAP_SHARE_POSITIONS):
        pairs = [
            (shares[key], row.touchdowns) for row in rows
            if row.season == season and row.position == position
            and (key := (row.player_id, row.season, row.week)) in shares
        ]
        model = LinearRegression(positive=True).fit([[share] for share, _ in pairs], [tds for _, tds in pairs])
        coefficients[position] = NflSnapCoefficients(float(model.intercept_), float(model.coef_[0]))
    return coefficients


def choose_snap_configuration(
    cases: list[NflTdBacktestCase], coefficients: dict[str, NflSnapCoefficients],
) -> tuple[SnapForm, float]:
    outcomes = [case.scored for case in cases]

    def fit_loss(configuration: tuple[SnapForm, float]) -> float:
        form, weight = configuration
        return log_loss([snap_share_probability(case, coefficients, form, weight) for case in cases], outcomes)

    return min(product(SNAP_FORMS, BLEND_WEIGHT_GRID), key=fit_loss)


def snap_report(
    rows: list[NflWeeklyTdRow], snap_rows: list[NflSnapRow], fit_season: int, holdout_season: int,
) -> str:
    coefficients = fit_snap_coefficients(rows, snap_rows, fit_season)
    fit_cases = [case for case in build_cases(rows, frozenset({fit_season}), snap_rows)
                 if case.position in SNAP_SHARE_POSITIONS]
    holdout_cases = [case for case in build_cases(rows, frozenset({holdout_season}), snap_rows)
                     if case.position in SNAP_SHARE_POSITIONS]
    form, weight = choose_snap_configuration(fit_cases, coefficients)
    snap = partial(snap_share_probability, coefficients_by_position=coefficients, form=form, blend_weight=weight)

    lines = [
        f"Coefficients (fit {fit_season}, TDs per game = intercept + per_share * snap share):",
        *(f"  {position}: intercept {value.intercept:.4f}, per_share {value.per_share:.4f}"
          for position, value in coefficients.items()),
        f"Form and blend weight (by {fit_season} RB+TE log loss): {form}, {weight:.1f}",
        "",
        _header("snap"),
        _line(f"{fit_season} RB+TE", score(fit_cases, baseline_probability), score(fit_cases, snap)),
        _line(f"{holdout_season} RB+TE", score(holdout_cases, baseline_probability), score(holdout_cases, snap)),
    ]
    baseline_positions = score_by_position(holdout_cases, baseline_probability)
    snap_positions = score_by_position(holdout_cases, snap)
    for position, baseline_score in baseline_positions.items():
        lines.append(_line(f"  {holdout_season} {position}", baseline_score, snap_positions[position]))
    return "\n".join(lines)


def choose_implied_total_configuration(
    cases: list[NflTdBacktestCase], league_average_implied_points: float,
) -> tuple[float, float]:
    outcomes = [case.scored for case in cases]

    def fit_loss(configuration: tuple[float, float]) -> float:
        exponent, weight = configuration
        probabilities = [
            implied_total_probability(case, league_average_implied_points, exponent, weight)
            for case in cases
        ]
        return log_loss(probabilities, outcomes)

    return min(product(IMPLIED_TOTAL_EXPONENT_GRID, BLEND_WEIGHT_GRID), key=fit_loss)


def implied_total_report(
    rows: list[NflWeeklyTdRow], snap_rows: list[NflSnapRow], fit_season: int, holdout_season: int,
) -> str:
    fit_cases = build_cases(rows, frozenset({fit_season}), snap_rows)
    holdout_cases = build_cases(rows, frozenset({holdout_season}), snap_rows)
    fit_implied = [
        implied_team_points(case.total_line, case.spread_line, case.is_home)
        for case in fit_cases
    ]
    league_average = mean(value for value in fit_implied if value is not None)
    exponent, weight = choose_implied_total_configuration(fit_cases, league_average)
    implied = partial(
        implied_total_probability, league_average_implied_points=league_average,
        exponent=exponent, blend_weight=weight,
    )

    lines = [
        f"Implied-total configuration (fit {fit_season} only): league average {league_average:.3f}, "
        f"exponent {exponent:.2f}, blend weight {weight:.1f}",
        "",
        _header("implied"),
        _line(f"{fit_season} fit", score(fit_cases, production_probability), score(fit_cases, implied)),
        _line(f"{holdout_season} holdout", score(holdout_cases, production_probability), score(holdout_cases, implied)),
    ]
    baseline_positions = score_by_position(holdout_cases, production_probability)
    implied_positions = score_by_position(holdout_cases, implied)
    for position, baseline_score in baseline_positions.items():
        lines.append(_line(f"  {holdout_season} {position}", baseline_score, implied_positions[position]))
    return "\n".join(lines)


def fit_end_zone_coefficients(rows: list[NflWeeklyTdRow], season: int) -> NflEndZoneCoefficients:
    """Fit WR/TE same-game TDs on same-game end-zone targets, using the fit season only."""
    pairs = [
        (row.end_zone_targets, row.touchdowns) for row in rows
        if row.season == season and row.position in END_ZONE_POSITIONS and row.end_zone_targets is not None
    ]
    model = LinearRegression(positive=True).fit([[targets] for targets, _ in pairs], [tds for _, tds in pairs])
    return NflEndZoneCoefficients(float(model.intercept_), float(model.coef_[0]))


def choose_end_zone_weight(cases: list[NflTdBacktestCase], coefficients: NflEndZoneCoefficients) -> float:
    outcomes = [case.scored for case in cases]
    return min(
        BLEND_WEIGHT_GRID,
        key=lambda weight: log_loss([end_zone_probability(case, coefficients, weight) for case in cases], outcomes),
    )


def end_zone_report(rows: list[NflWeeklyTdRow], snap_rows: list[NflSnapRow], fit_season: int, holdout_season: int) -> str:
    coefficients = fit_end_zone_coefficients(rows, fit_season)
    fit_cases = [case for case in build_cases(rows, frozenset({fit_season}), snap_rows) if case.position in END_ZONE_POSITIONS]
    holdout_cases = [case for case in build_cases(rows, frozenset({holdout_season}), snap_rows) if case.position in END_ZONE_POSITIONS]
    weight = choose_end_zone_weight(fit_cases, coefficients)
    end_zone = partial(end_zone_probability, coefficients=coefficients, blend_weight=weight)
    lines = [
        f"End-zone configuration (fit {fit_season} WR/TE only): intercept {coefficients.intercept:.4f}, "
        f"per target {coefficients.per_target:.4f}, blend weight {weight:.1f}",
        "",
        _header("end-zone"),
        _line(f"{fit_season} WR+TE", score(fit_cases, production_probability), score(fit_cases, end_zone)),
        _line(f"{holdout_season} WR+TE", score(holdout_cases, production_probability), score(holdout_cases, end_zone)),
    ]
    baseline_positions = score_by_position(holdout_cases, production_probability)
    end_zone_positions = score_by_position(holdout_cases, end_zone)
    for position, baseline_score in baseline_positions.items():
        lines.append(_line(f"  {holdout_season} {position}", baseline_score, end_zone_positions[position]))
    return "\n".join(lines)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    parser = argparse.ArgumentParser(description="Backtest a role signal for anytime TD")
    parser.add_argument("--signal", choices=("red-zone", "snap-share", "implied-total", "end-zone"), default="red-zone")
    parser.add_argument("--fit-season", type=int, default=2024)
    parser.add_argument("--holdout-season", type=int, default=2025)
    args = parser.parse_args()
    async with SessionLocal() as db:
        rows = await nfl_repo.get_weekly_td_rows(db)
        snap_rows = await nfl_repo.get_snap_rows(db) if args.signal in ("snap-share", "implied-total", "end-zone") else []
    if args.signal == "snap-share":
        print(snap_report(rows, snap_rows, args.fit_season, args.holdout_season))
    elif args.signal == "implied-total":
        print(implied_total_report(rows, snap_rows, args.fit_season, args.holdout_season))
    elif args.signal == "end-zone":
        print(end_zone_report(rows, snap_rows, args.fit_season, args.holdout_season))
    else:
        print(report(rows, args.fit_season, args.holdout_season))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
