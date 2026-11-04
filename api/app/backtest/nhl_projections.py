"""Replay NHL prop projections against a season's box scores (item 56b).

    python -m app.backtest.nhl_projections [--season 2024] [--arms reference,last_10]

2024-25 is development and may be replayed freely. 2025-26 is the holdout, scored once
per candidate. Only 2024-25 runs without `--holdout`; every other season is refused, so no run reads
the holdout (the season itself, or the season after it through its prior-season window) or anything
below the prior-season floor by accident.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence

from app.core.nfl_projection_backtest import market_metrics, paired
from app.core.nhl_projection_backtest import (
    ARMS,
    BACKTEST_MARKETS,
    DEVELOPMENT_SEASON,
    HOLDOUT_SEASON,
    MIN_PAIRED_CASES,
    MIN_PRIOR_GAMES,
    MIN_PRIOR_GOALIE_STARTS,
    MIN_PRIOR_TOI_MINUTES,
    MIN_RELATIVE_MAE_IMPROVEMENT,
    REFERENCE_ARM,
    STANDARD_ERRORS_REQUIRED,
    NhlReplayCase,
    nhl_adoption_verdict,
    replay_cases,
)

# The commit that fixed the rule, constants and arms before any NHL scoring existed.
PREREGISTRATION_COMMIT = "237c2bcc01caf68495c88982eedd4cdbf57da2a0"

RULE_TEXT = (
    f"Adopt a market only with >= {MIN_PAIRED_CASES} paired holdout cases, MAE at least "
    f"{MIN_RELATIVE_MAE_IMPROVEMENT:.0%} lower than {REFERENCE_ARM}, and a paired mean |error| difference "
    f"below zero by more than {STANDARD_ERRORS_REQUIRED:g} standard errors."
)
ELIGIBILITY_TEXT = (
    f"Cases: skaters with >= {MIN_PRIOR_GAMES} prior games and >= {MIN_PRIOR_TOI_MINUTES:g} mean TOI minutes over the "
    f"last 10; goalies who started with >= {MIN_PRIOR_GOALIE_STARTS} prior starts; Faceoffs Won for centers only."
)
GOALIE_CAVEAT = (
    "Goalie caveat: a goalie is a case only because he started, which is known after the game, so goalie error "
    "understates the uncertainty about who plays."
)

# Prior-TOI buckets for skaters: top-six and top-pair minutes sit above the lower bucket.
TOI_BUCKETS: tuple[tuple[str, float, float], ...] = (("12-16 min", 12.0, 16.0), ("16+ min", 16.0, float("inf")))

_MARKET_ORDER = [market.value for market in BACKTEST_MARKETS]


def season_label(season: int) -> str:
    return f"{season}-{(season + 1) % 100:02d}"


def seasons_to_read(season: int, holdout: bool) -> tuple[int, int]:
    """The season and the one before it, whose games supply early windows.

    Without `--holdout` only the development season runs, which keeps reads at or above the
    prior-season floor and away from 2025-26 and everything after it.
    """
    if holdout and season < HOLDOUT_SEASON:
        raise ValueError(f"--holdout is for {season_label(HOLDOUT_SEASON)} or later, not {season_label(season)}")
    if not holdout and season != DEVELOPMENT_SEASON:
        raise ValueError(
            f"only {season_label(DEVELOPMENT_SEASON)} runs without --holdout; {season_label(season)} would read "
            f"outside the development window or the {season_label(HOLDOUT_SEASON)} holdout. "
            "Pass --holdout only for a candidate's one scoring run",
        )
    return (season - 1, season)


def _role(season: int) -> str:
    if season == HOLDOUT_SEASON:
        return "HOLDOUT: each candidate arm is scored here once; fit nothing on it"
    if season == DEVELOPMENT_SEASON:
        return "development: replay and fit freely"
    return "not the development season; verdicts count only on the holdout"


def _header(season: int) -> list[str]:
    return [
        f"NHL projection backtest, {season_label(season)} ({_role(season)})",
        "",
        f"Pre-registered in commit {PREREGISTRATION_COMMIT}.",
        RULE_TEXT,
        ELIGIBILITY_TEXT,
        GOALIE_CAVEAT,
    ]


def _pct(value: float | None) -> str:
    return f"{value * 100:6.1f}%" if value is not None else "     --"


def _markets(cases: Sequence[NhlReplayCase]) -> list[str]:
    present = {case.market for case in cases}
    return [market for market in _MARKET_ORDER if market in present]


def _metrics_table(arm: str, cases: Sequence[NhlReplayCase]) -> list[str]:
    lines = [
        f"Arm {arm}: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)",
        f"  {'market / prior TOI':<34}{'n':>8}{'MAE':>9}{'RMSE':>9}{'bias':>9}{'below':>9}",
    ]
    for market in _markets(cases):
        in_market = [case for case in cases if case.market == market]
        groups = [("all", in_market)] + [
            (label, [case for case in in_market if case.prior_toi_minutes is not None and low <= case.prior_toi_minutes < high])
            for label, low, high in TOI_BUCKETS
        ]
        for label, group in groups:
            if not group:
                continue
            m = market_metrics(group)
            lines.append(
                f"  {market + ' / ' + label:<34}{m.n:>8}{m.mae:>9.3f}{m.rmse:>9.3f}{m.bias:>+9.3f}{_pct(m.share_below):>9}",
            )
    return lines


def _paired_table(arm: str, reference: Sequence[NhlReplayCase], variant: Sequence[NhlReplayCase]) -> list[str]:
    lines = [
        f"Arm {arm} against {REFERENCE_ARM}, paired on player, game and market",
        f"  {'market':<24}{'n':>8}{'ref MAE':>10}{'arm MAE':>10}{'change':>9}{'diff':>9}{'SE':>8}  verdict",
    ]
    for market in _markets(variant):
        in_market = [case for case in variant if case.market == market]
        diff = paired(reference, in_market)
        lines.append(
            f"  {market:<24}{diff.n:>8}{diff.production_mae:>10.3f}{diff.variant_mae:>10.3f}"
            f"{diff.relative_mae_change * 100:>+8.2f}%{diff.mean_diff:>+9.3f}{diff.standard_error:>8.3f}"
            f"  {nhl_adoption_verdict(diff)}",
        )
    return lines


def report(season: int, cases_by_arm: Mapping[str, Sequence[NhlReplayCase]]) -> str:
    lines = _header(season)
    for arm, cases in cases_by_arm.items():
        lines += ["", *_metrics_table(arm, cases)]
    reference = cases_by_arm[REFERENCE_ARM]
    for arm, cases in cases_by_arm.items():
        if arm != REFERENCE_ARM:
            lines += ["", *_paired_table(arm, reference, cases)]
    return "\n".join(lines)


def parse_arms(value: str) -> list[str]:
    arms = [arm.strip() for arm in value.split(",") if arm.strip()]
    unknown = [arm for arm in arms if arm not in ARMS]
    if unknown or REFERENCE_ARM not in arms:
        raise ValueError(f"arms must include {REFERENCE_ARM} and come from {sorted(ARMS)}; got {arms}")
    return arms


async def _main(season: int, arms: Sequence[str], seasons: tuple[int, int]) -> None:
    from sqlalchemy import text

    from app.db.pool import SessionLocal
    from app.repositories.nhl import get_projection_history

    async with SessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        history = await get_projection_history(db, seasons)
    print(report(season, {arm: replay_cases(history, season, ARMS[arm]) for arm in arms}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay NHL prop projections against a season's results")
    parser.add_argument("--season", type=int, default=DEVELOPMENT_SEASON)
    parser.add_argument("--arms", default=f"{REFERENCE_ARM},last_10")
    parser.add_argument("--holdout", action="store_true", help="allow reading the 2025-26 holdout")
    args = parser.parse_args()
    try:
        arm_names = parse_arms(args.arms)
        read_seasons = seasons_to_read(args.season, args.holdout)
    except ValueError as error:
        parser.error(str(error))
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, arm_names, read_seasons))
