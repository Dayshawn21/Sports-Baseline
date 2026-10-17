"""Replay NBA prop projections against a season's box scores (item 20f).

    python -m app.backtest.nba_projections [--season 2025] [--arms reference,last_10]

2025-26 is the holdout: each candidate arm is scored there once. Any other season is
development and may be replayed freely.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence

from app.core.nba_projection_backtest import (
    ARMS,
    BACKTEST_MARKETS,
    HOLDOUT_SEASON,
    MIN_PAIRED_CASES,
    MIN_RELATIVE_MAE_IMPROVEMENT,
    REFERENCE_ARM,
    STANDARD_ERRORS_REQUIRED,
    NbaReplayCase,
    nba_adoption_verdict,
    replay_cases,
)
from app.core.nfl_projection_backtest import market_metrics, paired

RULE_TEXT = (
    f"Adopt a market only with >= {MIN_PAIRED_CASES} paired holdout cases, MAE at least "
    f"{MIN_RELATIVE_MAE_IMPROVEMENT:.0%} lower than {REFERENCE_ARM}, and a paired mean |error| difference "
    f"below zero by more than {STANDARD_ERRORS_REQUIRED:g} standard errors (pre-registered 2026-10-06)."
)

# Prior-minutes buckets: rotation players, then starters' minutes.
MINUTES_BUCKETS: tuple[tuple[str, float, float], ...] = (("20-28 min", 20.0, 28.0), ("28+ min", 28.0, float("inf")))

_MARKET_ORDER = [market.value for market in BACKTEST_MARKETS]


def _season_label(season: int) -> str:
    return f"{season}-{(season + 1) % 100:02d}"


def _header(season: int) -> list[str]:
    if season == HOLDOUT_SEASON:
        role = "HOLDOUT: each candidate arm is scored here once; fit nothing on it"
    else:
        role = "development: replay and fit freely"
    return [f"NBA projection backtest, {_season_label(season)} ({role})", "", RULE_TEXT]


def _pct(value: float | None) -> str:
    return f"{value * 100:6.1f}%" if value is not None else "     --"


def _markets(cases: Sequence[NbaReplayCase]) -> list[str]:
    present = {case.market for case in cases}
    return [market for market in _MARKET_ORDER if market in present]


def _metrics_table(arm: str, cases: Sequence[NbaReplayCase]) -> list[str]:
    lines = [
        f"Arm {arm}: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)",
        f"  {'market / prior minutes':<36}{'n':>7}{'MAE':>9}{'RMSE':>9}{'bias':>9}{'below':>9}",
    ]
    for market in _markets(cases):
        in_market = [case for case in cases if case.market == market]
        groups = [("all", in_market)] + [
            (label, [case for case in in_market if low <= case.prior_minutes < high])
            for label, low, high in MINUTES_BUCKETS
        ]
        for label, group in groups:
            if not group:
                continue
            m = market_metrics(group)
            lines.append(
                f"  {market + ' / ' + label:<36}{m.n:>7}{m.mae:>9.2f}{m.rmse:>9.2f}{m.bias:>+9.2f}{_pct(m.share_below):>9}"
            )
    return lines


def _paired_table(arm: str, reference: Sequence[NbaReplayCase], variant: Sequence[NbaReplayCase]) -> list[str]:
    lines = [
        f"Arm {arm} against {REFERENCE_ARM}, paired on player, game and market",
        f"  {'market':<26}{'n':>7}{'ref MAE':>10}{'arm MAE':>10}{'change':>9}{'diff':>9}{'SE':>8}  verdict",
    ]
    for market in _markets(variant):
        in_market = [case for case in variant if case.market == market]
        diff = paired(reference, in_market)
        lines.append(
            f"  {market:<26}{diff.n:>7}{diff.production_mae:>10.3f}{diff.variant_mae:>10.3f}"
            f"{diff.relative_mae_change * 100:>+8.2f}%{diff.mean_diff:>+9.3f}{diff.standard_error:>8.3f}"
            f"  {nba_adoption_verdict(diff)}"
        )
    return lines


def report(season: int, cases_by_arm: Mapping[str, Sequence[NbaReplayCase]]) -> str:
    lines = _header(season)
    for arm, cases in cases_by_arm.items():
        lines += ["", *_metrics_table(arm, cases)]
    reference = cases_by_arm[REFERENCE_ARM]
    for arm, cases in cases_by_arm.items():
        if arm != REFERENCE_ARM:
            lines += ["", *_paired_table(arm, reference, cases)]
    return "\n".join(lines)


async def _main(season: int, arms: Sequence[str]) -> None:
    from app.db.pool import SessionLocal
    from app.repositories.nba import get_projection_history

    async with SessionLocal() as db:
        # The season before supplies early games' windows.
        history = await get_projection_history(db, (season - 1, season))
    print(report(season, {arm: replay_cases(history, season, ARMS[arm]) for arm in arms}))


def parse_arms(parser: argparse.ArgumentParser, value: str) -> list[str]:
    arms = [arm.strip() for arm in value.split(",") if arm.strip()]
    unknown = [arm for arm in arms if arm not in ARMS]
    if unknown or REFERENCE_ARM not in arms:
        parser.error(f"arms must include {REFERENCE_ARM} and come from {sorted(ARMS)}; got {arms}")
    return arms


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay NBA prop projections against a season's results")
    parser.add_argument("--season", type=int, default=HOLDOUT_SEASON)
    parser.add_argument("--arms", default=REFERENCE_ARM)
    args = parser.parse_args()
    arm_names = parse_arms(parser, args.arms)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, arm_names))
