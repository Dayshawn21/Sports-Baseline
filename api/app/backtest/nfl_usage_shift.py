"""Score the 70b3 usage-shift arms: the 2024 transfer pick, then one 2025 holdout read.

2024 is development and runs by default. 2025 is the holdout: it runs only with
`--holdout`, only for the committed `usage_shift` arm, and only after the pick is
committed. Every other season is refused. Only shifted rows are scored, against
production on the same player, game and market (an unshifted row is production).

It reads and prints. Nothing is fitted, stored, or fed back into a projection.

`--count-only` (2024) prints how many rated rows the transfer-1 arm shifts, and
how many rows lack a closing moneyline, with no projection, error or actual.

Run from api/: python -m app.backtest.nfl_usage_shift [--count-only | --season 2025 --holdout]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence

from app.backtest.nfl_projections import PRODUCTION_ARM, REGULAR_SEASON_WEEKS, USAGE_SHIFT_ARM, replay_cases
from app.core.nfl_projection_backtest import MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED, ReplayCase
from app.core.nfl_usage_shift import SHIFT_MARKETS
from app.core.nfl_usage_shift_rule import (
    USAGE_SHIFT_MAX_MULTIPLIER, USAGE_SHIFT_MIN_OWN_VOLUME, USAGE_SHIFT_MIN_SHIFTED_CASES,
    USAGE_SHIFT_PREREGISTRATION_COMMIT, USAGE_SHIFT_TRANSFER_BY_MARKET, USAGE_SHIFT_TRANSFER_GRID, pick_transfer,
    shifted_paired, usage_shift_arm_name, usage_shift_verdict,
)

DEVELOPMENT_SEASON = 2024
HOLDOUT_SEASON = 2025
DEVELOPMENT_ARMS = (PRODUCTION_ARM, *(usage_shift_arm_name(transfer) for transfer in USAGE_SHIFT_TRANSFER_GRID))
HOLDOUT_ARMS = (PRODUCTION_ARM, USAGE_SHIFT_ARM)

RULE_LINES = (
    f"Usage shift: a fresh Out RB/WR/TE on this week's chart hands transfer x his season-to-date carries or "
    f"targets per game to the teammate whose active rank takes his place; that teammate's market average "
    f"scales by (own + gained) / own, capped at {USAGE_SHIFT_MAX_MULTIPLIER:g}; a teammate "
    f"under {USAGE_SHIFT_MIN_OWN_VOLUME:g} own carries or targets per game is not scaled.",
    f"Selection (2024): per market, the transfer of 0, "
    f"{', '.join(f'{t:g}' for t in USAGE_SHIFT_TRANSFER_GRID)} with the lowest MAE on shifted rows, ties to the "
    f"smaller; a market that picks 0 is not a holdout candidate.",
    f"Holdout (2025, once): adopt a market only with >= {USAGE_SHIFT_MIN_SHIFTED_CASES} paired shifted cases, "
    f"MAE at least {MIN_RELATIVE_MAE_IMPROVEMENT:.0%} lower than production, and a paired mean |error| "
    f"difference below zero by more than {STANDARD_ERRORS_REQUIRED:g} standard errors.",
)


def season_error(season: int, holdout: bool, transfer_by_market: Mapping[str, float]) -> str | None:
    """Why this run may not read `season`, or None when it may."""
    if holdout:
        if season != HOLDOUT_SEASON:
            return f"--holdout reads {HOLDOUT_SEASON} only"
        if not any(transfer > 0 for transfer in transfer_by_market.values()):
            return "no market has a committed transfer above 0, so there is no holdout candidate"
        return None
    if season != DEVELOPMENT_SEASON:
        return (
            f"only {DEVELOPMENT_SEASON}, the development season, runs without --holdout; "
            f"{HOLDOUT_SEASON} is the holdout and needs a separate yes"
        )
    return None


def _header(season: int) -> list[str]:
    commit = (
        f"Rule pre-registered in commit {USAGE_SHIFT_PREREGISTRATION_COMMIT}."
        if USAGE_SHIFT_PREREGISTRATION_COMMIT else "Rule not yet committed."
    )
    return [f"NFL usage-shift backtest, {season}", commit, *RULE_LINES]


def _in_market(cases: Sequence[ReplayCase], market: str) -> list[ReplayCase]:
    return [case for case in cases if case.market == market]


def development_report(cases_by_arm: Mapping[str, Sequence[ReplayCase]]) -> str:
    production = cases_by_arm[PRODUCTION_ARM]
    transfers = (0.0, *USAGE_SHIFT_TRANSFER_GRID)
    lines = [
        *_header(DEVELOPMENT_SEASON), "", "Transfer pick per market (MAE on shifted rows)",
        f"  {'market':<20}{'n':>6}" + "".join(f"{'t ' + format(t, 'g'):>10}" for t in transfers) + "    pick",
    ]
    for market in SHIFT_MARKETS:
        diffs = {}
        for transfer in USAGE_SHIFT_TRANSFER_GRID:
            variant = _in_market(cases_by_arm[usage_shift_arm_name(transfer)], market)
            if any(case.shifted for case in variant):
                diffs[transfer] = shifted_paired(_in_market(production, market), variant)
        if not diffs:
            lines.append(f"  {market:<20}{0:>6}    no shifted rows; pick 0")
            continue
        # Every grid point shifts the same rows, so production's MAE on them is one number.
        mae = {0.0: next(iter(diffs.values())).production_mae} | {t: d.variant_mae for t, d in diffs.items()}
        n = ",".join(sorted({str(d.n) for d in diffs.values()}))
        lines.append(
            f"  {market:<20}{n:>6}" + "".join(f"{mae[t]:>10.3f}" for t in transfers) + f"{pick_transfer(mae):>8g}"
        )
    return "\n".join(lines)


def holdout_report(cases_by_arm: Mapping[str, Sequence[ReplayCase]], transfer_by_market: Mapping[str, float]) -> str:
    production, variant = cases_by_arm[PRODUCTION_ARM], cases_by_arm[USAGE_SHIFT_ARM]
    lines = [
        *_header(HOLDOUT_SEASON), "", "Committed usage_shift against production on shifted rows",
        f"  {'market':<20}{'transfer':>9}{'n':>6}{'prod MAE':>10}{'var MAE':>10}{'change':>9}{'diff':>9}{'SE':>8}  verdict",
    ]
    for market in SHIFT_MARKETS:
        transfer = transfer_by_market.get(market, 0.0)
        in_market = _in_market(variant, market)
        if transfer == 0 or not any(case.shifted for case in in_market):
            reason = "not a candidate" if transfer == 0 else "no shifted rows"
            lines.append(f"  {market:<20}{transfer:>9g}    {reason}")
            continue
        diff = shifted_paired(_in_market(production, market), in_market)
        lines.append(
            f"  {market:<20}{transfer:>9g}{diff.n:>6}{diff.production_mae:>10.3f}{diff.variant_mae:>10.3f}"
            f"{diff.relative_mae_change * 100:>+8.2f}%{diff.mean_diff:>+9.3f}{diff.standard_error:>8.3f}"
            f"  {usage_shift_verdict(diff)}"
        )
    return "\n".join(lines)


COUNT_ARM = usage_shift_arm_name(max(USAGE_SHIFT_TRANSFER_GRID))


def count_report(cases: Sequence[ReplayCase], rows: int, rows_without_moneyline: int) -> str:
    """Rated and shifted rows per market; reads no projection, error or actual."""
    lines = [
        f"NFL usage-shift counts, {DEVELOPMENT_SEASON}, arm {COUNT_ARM} (counts only; no projection, error or result)",
        f"min_own_volume={USAGE_SHIFT_MIN_OWN_VOLUME:g} max_multiplier={USAGE_SHIFT_MAX_MULTIPLIER:g}; "
        f"holdout minimum {USAGE_SHIFT_MIN_SHIFTED_CASES} shifted cases",
        f"Replay rows: {rows}; without a closing moneyline: {rows_without_moneyline}",
        "",
        f"  {'market':<20}{'rated':>8}{'shifted':>9}",
    ]
    for market in SHIFT_MARKETS:
        in_market = _in_market(cases, market)
        lines.append(f"  {market:<20}{len(in_market):>8}{sum(case.shifted for case in in_market):>9}")
    return "\n".join(lines)


async def _count(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    cases: list[ReplayCase] = []
    rows = without_moneyline = 0
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            replay = await nfl_repo.get_replay_rows(db, season, week)
            rows += len(replay)
            without_moneyline += sum(row.home_market_prob is None for row in replay)
            cases += replay_cases(replay, COUNT_ARM, season, week)
    print(count_report(cases, rows, without_moneyline))


async def _main(season: int, holdout: bool) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    arms = HOLDOUT_ARMS if holdout else DEVELOPMENT_ARMS
    cases_by_arm: dict[str, list[ReplayCase]] = {arm: [] for arm in arms}
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows = await nfl_repo.get_replay_rows(db, season, week)
            for arm in arms:
                cases_by_arm[arm] += replay_cases(rows, arm, season, week)
    print(holdout_report(cases_by_arm, USAGE_SHIFT_TRANSFER_BY_MARKET) if holdout else development_report(cases_by_arm))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the 70b3 NFL usage-shift arms")
    parser.add_argument("--season", type=int, default=DEVELOPMENT_SEASON)
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args()
    error = season_error(args.season, args.holdout, USAGE_SHIFT_TRANSFER_BY_MARKET)
    if args.count_only and args.holdout:
        error = "--count-only reads the development season only"
    if error:
        parser.error(error)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_count(args.season) if args.count_only else _main(args.season, args.holdout))


if __name__ == "__main__":
    main()
