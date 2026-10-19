"""Replay a season of NFL prop projections against results, per arm, and judge each variant.

Every QB/RB/WR/TE player-game that recorded a stat is projected through the
slate's own `_slate_line` with pre-week inputs only, for each market its
position is bet on. The one input that differs from what was served is the
moneyline: the game's de-vigged closing line, since no live odds were stored
for 2025. Only rows that would receive an edge (enough baseline games) are
scored. The gate for 27c-27f; see `adoption_verdict` for the pre-registered rule.

It reads and prints. Nothing is fitted, stored, or fed back into a projection.

Run from api/: python -m app.backtest.nfl_projections [--season 2025] [--arms production,wind]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION, edge_is_comparable
from app.core.nfl_projection_backtest import (
    MIN_PAIRED_CASES, MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED, ReplayCase, ReplayRow,
    adoption_verdict, market_metrics, paired,
)
from app.core.nfl_fantasy import apply_prizepicks_fantasy
from app.core.nfl_game_environment import apply_game_environment
from app.core.nfl_season_blend import apply_season_blend, blended_row
from app.core.nfl_team_game_dvp import apply_team_game_dvp
from app.core.nfl_wind import WIND_MARKETS, apply_wind
from app.nfl.markets import NFL_V4_PROP_MARKETS, NflPropMarket
from app.services.nfl.slate import _slate_line

PRODUCTION_ARM = "production"
REGULAR_SEASON_WEEKS = range(1, 19)
ENVIRONMENT_ARM_MARKETS = NFL_V4_PROP_MARKETS - {NflPropMarket.ANYTIME_TOUCHDOWN}


def _production(row: dict, season: int) -> dict:
    """What the slate serves, including 27c's and 27d's adopted markets."""
    return apply_season_blend(apply_team_game_dvp(row), season)


ARMS: dict[str, Callable[[dict, int], dict]] = {
    PRODUCTION_ARM: _production,
    "usage_off": lambda row, season: {**row, "usage": None},
    # 27c: defense-versus-position from per-game position totals over a 17-game window.
    "dvp_team_game": lambda row, season: {
        **row,
        "opponent_averages": row["team_game_opponent_averages"],
        "league_position_averages": row["team_game_league_averages"],
    },
    # 27d: current and previous season blended by games, stacked on production.
    "season_blend": lambda row, season: blended_row(apply_team_game_dvp(row), season),
    # 27e: game environment in place of moneyline scaling, every non-TD market, stacked on production.
    "game_environment": lambda row, season: apply_game_environment(_production(row, season), ENVIRONMENT_ARM_MARKETS),
    # 27f: fantasy projected from PrizePicks points instead of NFLverse PPR, stacked on production. Rejected.
    "prizepicks_fantasy": lambda row, season: _production(apply_prizepicks_fantasy(row), season),
    # 27k: observed wind for the three passing markets, stacked on production.
    "wind": lambda row, season: apply_wind(_production(row, season), WIND_MARKETS),
}

RULE_TEXT = (
    f"Adopt a market only with >= {MIN_PAIRED_CASES} paired cases, MAE at least "
    f"{MIN_RELATIVE_MAE_IMPROVEMENT:.0%} lower than production, and a paired mean |error| difference "
    f"below zero by more than {STANDARD_ERRORS_REQUIRED:g} standard errors (pre-registered 2026-09-26)."
)


def replay_cases(rows: Iterable[ReplayRow], arm: str, season: int, week: int) -> list[ReplayCase]:
    transform = ARMS[arm]
    cases = []
    for replay in rows:
        line = _slate_line(transform(replay.row, season), season, replay.home_market_prob)
        rated = edge_is_comparable(NflPropMarket(line.market), line.games_in_sample, line.segment, line.odds_type)
        if line.projection is None or not rated:
            continue
        cases.append(ReplayCase(
            player_id=line.player_id, game_id=replay.row["game_id"], week=week, position=line.position,
            market=line.market, projection=line.projection, actual=replay.actual,
        ))
    return cases


def _pct(value: float | None) -> str:
    return f"{value * 100:6.1f}%" if value is not None else "     --"


def _metrics_table(arm: str, cases: Sequence[ReplayCase]) -> list[str]:
    lines = [
        f"Arm {arm}: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)",
        f"  {'market / position':<30}{'n':>7}{'MAE':>9}{'RMSE':>9}{'bias':>9}{'below':>9}",
    ]
    for market in sorted({case.market for case in cases}):
        in_market = [case for case in cases if case.market == market]
        groups = [("all", in_market)] + [
            (position, [case for case in in_market if case.position == position])
            for position in sorted({case.position for case in in_market})
        ]
        for position, group in groups:
            m = market_metrics(group)
            lines.append(
                f"  {market + ' / ' + position:<30}{m.n:>7}{m.mae:>9.2f}{m.rmse:>9.2f}{m.bias:>+9.2f}{_pct(m.share_below):>9}"
            )
    return lines


def _paired_table(arm: str, production: Sequence[ReplayCase], variant: Sequence[ReplayCase]) -> list[str]:
    lines = [
        f"Variant {arm} against production, paired on player, game and market",
        f"  {'market':<22}{'n':>7}{'prod MAE':>10}{'var MAE':>10}{'change':>9}{'diff':>9}{'SE':>8}  verdict",
    ]
    for market in sorted({case.market for case in variant}):
        in_market = [case for case in variant if case.market == market]
        diff = paired(production, in_market)
        lines.append(
            f"  {market:<22}{diff.n:>7}{diff.production_mae:>10.3f}{diff.variant_mae:>10.3f}"
            f"{diff.relative_mae_change * 100:>+8.2f}%{diff.mean_diff:>+9.3f}{diff.standard_error:>8.3f}"
            f"  {adoption_verdict(diff)}"
        )
    return lines


def report(season: int, cases_by_arm: Mapping[str, Sequence[ReplayCase]]) -> str:
    lines = [f"NFL projection backtest, {season} (model {NFL_PROJECTION_MODEL_VERSION})", "", RULE_TEXT]
    for arm, cases in cases_by_arm.items():
        lines += ["", *_metrics_table(arm, cases)]
    production = cases_by_arm[PRODUCTION_ARM]
    for arm, cases in cases_by_arm.items():
        if arm != PRODUCTION_ARM:
            lines += ["", *_paired_table(arm, production, cases)]
    return "\n".join(lines)


async def _main(season: int, arms: Sequence[str]) -> None:
    from app.db.pool import SessionLocal
    from app.repositories import nfl as nfl_repo

    cases_by_arm: dict[str, list[ReplayCase]] = {arm: [] for arm in arms}
    async with SessionLocal() as db:
        for week in REGULAR_SEASON_WEEKS:
            rows = await nfl_repo.get_replay_rows(db, season, week)
            for arm in arms:
                cases_by_arm[arm] += replay_cases(rows, arm, season, week)
    print(report(season, cases_by_arm))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay NFL prop projections against a season's results")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--arms", default=f"{PRODUCTION_ARM},wind")
    args = parser.parse_args()
    arm_names = [arm.strip() for arm in args.arms.split(",")]
    unknown = [arm for arm in arm_names if arm not in ARMS]
    if unknown or PRODUCTION_ARM not in arm_names:
        parser.error(f"arms must include {PRODUCTION_ARM} and come from {sorted(ARMS)}; got {arm_names}")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season, arm_names))
